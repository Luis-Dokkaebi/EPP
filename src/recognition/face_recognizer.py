import os
import io
import cv2
import numpy as np
import shutil
import hashlib
import hmac as _hmac_mod
import platform
import logging

_logger = logging.getLogger(__name__)

try:
    import face_recognition
except ImportError:
    _logger.warning("face_recognition module not found. Face recognition will not work.")
    face_recognition = None


def _get_integrity_key() -> bytes:
    """Clave HMAC específica de la máquina — liga el archivo de encodings a esta PC.

    CR-08 / P2-2: derivar del MISMO `machine_id` (WMI) que usa el DRM, no del
    hostname (`platform.node()`), que es trivialmente modificable (renombrar la PC,
    unirse a un dominio AD) e invalidaría la biometría. Consistente con
    `db_crypto.py` y `crash_logger.py`. Bump a `v2` para no colisionar con firmas
    viejas (las `.npz` firmadas con v1 se re-codifican desde las imágenes).
    """
    try:
        from src.security.drm import DRMValidator
        machine_id = DRMValidator().machine_id
    except Exception:
        import uuid
        machine_id = f"FALLBACK_{uuid.getnode()}"
    return hashlib.sha256(machine_id.encode("utf-8") + b"_oe_face_integrity_v2").digest()


def _sign(data: bytes) -> bytes:
    return _hmac_mod.new(_get_integrity_key(), data, hashlib.sha256).digest()


def _verify(data: bytes, sig: bytes) -> bool:
    return _hmac_mod.compare_digest(_sign(data), sig)


class FaceRecognizer:
    def __init__(self, faces_dir=None, encodings_file=None):
        if faces_dir is None:
            data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'OficinaEficiencia', 'data')
            self.faces_dir = os.path.join(data_dir, 'faces')
        else:
            self.faces_dir = faces_dir

        if encodings_file is None:
            self.encodings_file = os.path.join(self.faces_dir, 'encodings.npz')
        else:
            self.encodings_file = encodings_file

        self.known_face_encodings = []
        self.known_face_names = []
        self._encodings_mtime = 0

        os.makedirs(self.faces_dir, exist_ok=True)
        self.load_known_faces()

    def load_known_faces(self):
        """Loads known faces from disk. Uses numpy format with HMAC integrity check."""
        if face_recognition is None:
            return

        if os.path.exists(self.encodings_file):
            try:
                with open(self.encodings_file, 'rb') as f:
                    raw = f.read()

                _HMAC_LEN = 32  # SHA-256 digest length
                if len(raw) < _HMAC_LEN:
                    raise ValueError("File too short — corrupted or legacy format")

                sig, payload = raw[:_HMAC_LEN], raw[_HMAC_LEN:]
                if not _verify(payload, sig):
                    raise ValueError("HMAC integrity check failed — file may be tampered or from another machine")

                loaded = np.load(io.BytesIO(payload), allow_pickle=False)
                enc = loaded['encodings']
                names = loaded['names']

                self.known_face_encodings = [enc[i] for i in range(len(enc))] if len(enc) > 0 else []
                self.known_face_names = [str(n) for n in names]
                self._encodings_mtime = os.path.getmtime(self.encodings_file)
                _logger.info("[FaceRecognizer] Loaded %d face(s).", len(self.known_face_names))
                return
            except Exception as e:
                _logger.warning("[FaceRecognizer] Could not load encodings (%s). Re-encoding from images.", type(e).__name__)

        # Migrate from legacy pickle format (one-time migration, then delete old file)
        legacy_pkl = os.path.splitext(self.encodings_file)[0] + '.pkl'
        if legacy_pkl != self.encodings_file and os.path.exists(legacy_pkl):
            try:
                import pickle  # noqa: S403 — controlled one-time migration from trusted local file
                with open(legacy_pkl, 'rb') as f:
                    data = pickle.load(f)  # noqa: S301  # nosec B301  # WAIVER-#6
                self.known_face_encodings = data.get('encodings', [])
                self.known_face_names = data.get('names', [])
                _logger.info("[FaceRecognizer] Migrating %d encoding(s) from legacy .pkl to .npz.", len(self.known_face_names))
                self.save_encodings()
                return
            except Exception as e:
                _logger.warning("[FaceRecognizer] Legacy .pkl migration failed (%s). Re-encoding.", type(e).__name__)

        _logger.info("[FaceRecognizer] Encoding faces from image directory...")
        self.known_face_encodings = []
        self.known_face_names = []

        if not os.path.exists(self.faces_dir):
            return

        for name in os.listdir(self.faces_dir):
            person_dir = os.path.join(self.faces_dir, name)
            if not os.path.isdir(person_dir):
                continue

            for filename in os.listdir(person_dir):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    filepath = os.path.join(person_dir, filename)
                    image = face_recognition.load_image_file(filepath)
                    encodings = face_recognition.face_encodings(image)

                    if encodings:
                        self.known_face_encodings.append(encodings[0])
                        self.known_face_names.append(name)
                    else:
                        _logger.debug("[FaceRecognizer] No face found in %s", filename)

        self.save_encodings()

    def save_encodings(self):
        """Saves encodings as numpy compressed format with HMAC integrity signature."""
        if self.known_face_encodings:
            encodings_arr = np.array(self.known_face_encodings, dtype=np.float64)
        else:
            encodings_arr = np.empty((0, 128), dtype=np.float64)
        names_arr = np.array(self.known_face_names, dtype=str)

        buf = io.BytesIO()
        np.savez_compressed(buf, encodings=encodings_arr, names=names_arr)
        payload = buf.getvalue()
        sig = _sign(payload)

        with open(self.encodings_file, 'wb') as f:
            f.write(sig + payload)

        self._encodings_mtime = os.path.getmtime(self.encodings_file)
        _logger.info("[FaceRecognizer] Saved %d encoding(s).", len(self.known_face_names))

    def check_reload(self):
        """
        Hot-reload: checks if encodings file was modified by another process and reloads if so.
        Enables CameraWorker to pick up newly registered faces without restart.
        """
        if not os.path.exists(self.encodings_file):
            return
        try:
            current_mtime = os.path.getmtime(self.encodings_file)
            if current_mtime > self._encodings_mtime:
                _logger.info("[FaceRecognizer] Encodings file changed on disk. Hot-reloading...")
                self.load_known_faces()
        except Exception as e:
            _logger.warning("[FaceRecognizer] Error checking reload: %s", type(e).__name__)

    def recognize_face(self, frame, bbox=None):
        """Recognizes a face in the frame. Returns the name or 'Unknown'."""
        if face_recognition is None:
            return "Unknown"

        if bbox:
            x1, y1, x2, y2 = map(int, bbox)
            h, w, _ = frame.shape
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)
            face_image = frame[y1:y2, x1:x2]
        else:
            face_image = frame

        rgb_face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_face_image)
        if not face_locations:
            return "Unknown"

        face_encodings = face_recognition.face_encodings(rgb_face_image, face_locations)
        if not face_encodings:
            return "Unknown"

        encoding = face_encodings[0]

        if not self.known_face_encodings:
            return "Unknown"

        matches = face_recognition.compare_faces(self.known_face_encodings, encoding, tolerance=0.65)
        name = "Unknown"

        face_distances = face_recognition.face_distance(self.known_face_encodings, encoding)
        best_match_index = np.argmin(face_distances)

        if matches[best_match_index]:
            name = self.known_face_names[best_match_index]

        return name

    def register_face(self, image_path, name):
        """Registers a new face from an image file."""
        if face_recognition is None:
            _logger.warning("Face recognition module not available.")
            return False

        if not os.path.exists(image_path):
            _logger.warning("Image path does not exist: registration aborted.")
            return False

        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)

        if not encodings:
            _logger.info("No face found in the provided image.")
            return False

        encoding = encodings[0]

        person_dir = os.path.join(self.faces_dir, name)
        os.makedirs(person_dir, exist_ok=True)

        filename = os.path.basename(image_path)
        dest_path = os.path.join(person_dir, filename)
        shutil.copy(image_path, dest_path)

        self.known_face_encodings.append(encoding)
        self.known_face_names.append(name)

        self.save_encodings()
        _logger.info("[FaceRecognizer] Registered '%s' successfully.", name)
        return True

    def register_face_burst(self, image_paths, name):
        """Registers a face from multiple burst images. Returns number of successful registrations."""
        if face_recognition is None:
            _logger.warning("Face recognition module not available.")
            return 0

        person_dir = os.path.join(self.faces_dir, name)
        os.makedirs(person_dir, exist_ok=True)

        success_count = 0
        for idx, image_path in enumerate(image_paths):
            if not os.path.exists(image_path):
                continue
            try:
                image = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(image)

                if not encodings:
                    _logger.debug("No face found in burst image %d", idx)
                    continue

                encoding = encodings[0]
                dest_path = os.path.join(person_dir, f"burst_{idx}.jpg")
                shutil.copy(image_path, dest_path)

                self.known_face_encodings.append(encoding)
                self.known_face_names.append(name)
                success_count += 1
            except Exception as e:
                _logger.warning("[FaceRecognizer] Error processing burst image %d: %s", idx, type(e).__name__)

        if success_count > 0:
            self.save_encodings()
            _logger.info("[FaceRecognizer] Registered '%s' with %d burst image(s).", name, success_count)

        return success_count

    def delete_face(self, name):
        """Removes a face from memory and disk."""
        if name not in self.known_face_names:
            _logger.warning("[FaceRecognizer] Employee not found in memory: deletion aborted.")
            return False

        indexes_to_delete = [i for i, n in enumerate(self.known_face_names) if n == name]
        for index in sorted(indexes_to_delete, reverse=True):
            del self.known_face_names[index]
            del self.known_face_encodings[index]

        self.save_encodings()

        person_dir = os.path.join(self.faces_dir, name)
        if os.path.exists(person_dir):
            try:
                shutil.rmtree(person_dir)
            except Exception as e:
                _logger.warning("[FaceRecognizer] Error deleting face directory: %s", type(e).__name__)

        _logger.info("[FaceRecognizer] Deleted '%s' successfully.", name)
        return True
