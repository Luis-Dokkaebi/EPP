# src/gui_app.py
import os
import sys
import traceback
import datetime

def global_exception_handler(exctype, value, tb):
    log_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'OficinaEficiencia')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'crash_log.txt')
    import time
    with open(log_path, 'a') as f:
        f.write(f"\n--- CRASH {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        traceback.print_exception(exctype, value, tb, file=f)
    print(f"CRASH LOGGED TO {log_path}")
    try:
        import tkinter.messagebox
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        tkinter.messagebox.showerror("Error Fatal", f"La aplicación se cerró inesperadamente.\nRevisa el log en: {log_path}\n\nError: {value}")
    except:
        pass

sys.excepthook = global_exception_handler

# Prevent duplicate library OpenMP OMP: Error #15 crash upon loading torch/numpy together
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# CRITICAL PRIORITY PRELOAD: Torch must be imported BEFORE EVERYTHING ELSE (cv2, numpy, ultralytics).
# If cv2 loads first, it poisons Windows memory with an incompatible 600KB Conda libiomp5md.dll,
# crashing PyTorch's shm.dll with WinError 127. By calling torch first, we inject the 1.6MB master DLL!
import torch

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import cv2
from PIL import Image, ImageTk
import sys
import subprocess
import threading
from src.gui.selector_fecha import (
    FechaInvalidaError,
    RangoDeFechasInvalidoError,
    SelectorDeFecha,
    consultar_reporte,
)
import pandas as pd
from datetime import datetime, date, timedelta

import sys
import subprocess
import threading

# Add the project root directory to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.storage.database_manager import DatabaseManager

# Explicitly import main so PyInstaller bundles all its heavy dependencies (ultralytics, supervision)
from src import main
from src.recognition.face_recognizer import FaceRecognizer
import face_recognition

class SystemGUI:
    def __init__(self, root):
        self.root = root
        from config.config import VERSION
        self.root.title(f"Control de Asistencia y Monitoreo v{VERSION} - Configuración")
        self.root.geometry("800x600")
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Configs
        try:
            from config.config import FACES_DIR
            self.faces_dir = FACES_DIR
        except ImportError:
            data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'OficinaEficiencia', 'data')
            self.faces_dir = os.path.join(data_dir, 'faces')
            os.makedirs(self.faces_dir, exist_ok=True)
        self.face_recognizer = FaceRecognizer(faces_dir=self.faces_dir)

        self.db = DatabaseManager()

        # Privacy: Admin session state for revealing anonymized snapshots
        self.is_admin_unlocked = False
        # SHA-256 hash of the admin password (default: 'admin123')
        import hashlib
        self.ADMIN_PASSWORD_HASH = hashlib.sha256('admin123'.encode()).hexdigest()

        self.current_frame = None
        self.available_cameras = self._enumerate_cameras()
        self.cap = None
        self.selected_camera_index = None

        # Face detection for live BB overlay (lightweight Haar Cascade)
        # Resolve haar cascade path robustly for both dev and PyInstaller environments
        haar_filename = 'haarcascade_frontalface_default.xml'
        haar_candidates = [
            os.path.join(cv2.data.haarcascades, haar_filename),                     # Normal Python environment
            os.path.join(os.path.dirname(cv2.__file__), 'data', haar_filename),     # Some OpenCV installs
            os.path.join(getattr(sys, '_MEIPASS', '.'), 'cv2', 'data', haar_filename),  # PyInstaller _internal
            os.path.join('.', haar_filename),                                        # Current directory fallback
        ]
        haar_path = None
        for candidate in haar_candidates:
            if os.path.exists(candidate):
                haar_path = candidate
                break
        if haar_path is None:
            print(f"⚠️ No se encontró {haar_filename}. Bounding box deshabilitado.")
            haar_path = haar_candidates[0]  # Use default, CascadeClassifier will just be empty
        self.face_cascade = cv2.CascadeClassifier(haar_path)

        # Quality semaphore state: 'red', 'yellow', 'green'
        self.quality_state = 'red'
        self.detected_face_rect = None  # (x,y,w,h) of detected face in display coords

        # Tint feedback after capture (green=success, red=error)
        self.tint_color = None   # None, 'green', 'red'
        self.tint_until = 0      # timestamp until tint expires

        # Countdown / burst capture state machine
        self.countdown_value = 0       # 3,2,1 -> 0 means idle
        self.burst_frames = []         # collected burst frames
        self.is_capturing = False      # True during countdown+burst
        # Liveness
        self.liveness_confirmed = False
        self.prev_gray_face = None

        # Background calibration
        self.background_reference = None
        self.bg_subtractor = None

        self._build_ui()
        # Auto-select best camera on startup
        self._auto_select_camera()
        if self.cap is not None:
            self._update_video()

    def _enumerate_cameras(self):
        """Escanea índices 0-4 y devuelve lista de cámaras disponibles [(index, label)]."""
        cameras = []
        for idx in range(5):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                # Read backend name if available
                backend = cap.getBackendName() if hasattr(cap, 'getBackendName') else 'unknown'
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                label = f"Cámara {idx} ({w}x{h}, {backend})"
                cameras.append((idx, label))
                cap.release()
            else:
                cap.release()
        print(f"📷 Cámaras detectadas: {cameras}")
        return cameras

    def _auto_select_camera(self):
        """Selecciona automáticamente la primera cámara que devuelve frames."""
        if not self.available_cameras:
            messagebox.showerror("Error", "No se detectó ninguna cámara conectada al equipo.")
            return

        # Try each in order, pick first that returns a frame
        for idx, label in self.available_cameras:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    self.cap = cap
                    self.selected_camera_index = idx
                    print(f"✅ Cámara auto-seleccionada: {label}")
                    # Update combobox selection
                    if hasattr(self, 'camera_combo'):
                        for i, (cidx, _) in enumerate(self.available_cameras):
                            if cidx == idx:
                                self.camera_combo.current(i)
                                break
                    return
                cap.release()

        messagebox.showerror("Error", "Ninguna cámara devolvió imagen. Verifica los drivers de la cámara.")

    def _switch_camera(self, event=None):
        """Cambia a la cámara seleccionada en el combobox."""
        selection = self.camera_combo.current()
        if selection < 0 or selection >= len(self.available_cameras):
            return

        new_idx, label = self.available_cameras[selection]
        if new_idx == self.selected_camera_index:
            return  # Same camera, nothing to do

        # Release old camera
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        # Open new camera
        cap = cv2.VideoCapture(new_idx)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                self.cap = cap
                self.selected_camera_index = new_idx
                print(f"🔄 Cámara cambiada a: {label}")
                # Restart video loop if it wasn't running
                if not hasattr(self, '_video_running') or not self._video_running:
                    self._video_running = True
                    self._update_video()
                return
            cap.release()

        messagebox.showerror("Error", f"No se pudo abrir la cámara: {label}")
        # Try to revert to old camera
        if self.selected_camera_index is not None:
            self.cap = cv2.VideoCapture(self.selected_camera_index)

    def _refresh_cameras(self):
        """Re-escanea las cámaras disponibles (e.g. si se conecta una nueva USB)."""
        self.available_cameras = self._enumerate_cameras()
        if hasattr(self, 'camera_combo'):
            labels = [label for _, label in self.available_cameras]
            self.camera_combo['values'] = labels if labels else ['No se detectó cámara']
            # Try to keep selection
            found = False
            for i, (idx, _) in enumerate(self.available_cameras):
                if idx == self.selected_camera_index:
                    self.camera_combo.current(i)
                    found = True
                    break
            if not found and labels:
                self.camera_combo.current(0)

    def _build_ui(self):
        # Create Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        
        # Tabs
        self.tab_registro = ttk.Frame(self.notebook)
        self.tab_asistencia = ttk.Frame(self.notebook)
        self.tab_eficiencia = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_registro, text="Configuración / Registro")
        self.notebook.add(self.tab_asistencia, text="Reporte de Asistencia")
        self.notebook.add(self.tab_eficiencia, text="Reporte de Eficiencia")
        
        self._build_registration_tab(self.tab_registro)
        self._build_attendance_tab(self.tab_asistencia)
        self._build_efficiency_tab(self.tab_eficiencia)

    def _build_registration_tab(self, parent_frame):
        # Configure grid for this tab (2 columns)
        parent_frame.columnconfigure(0, weight=3) # Video side
        parent_frame.columnconfigure(1, weight=2) # Controls side
        
        # Row 0: Header (Full Width)
        header = tk.Label(parent_frame, text="Registro e Infraestructura", font=("Arial", 18, "bold"))
        header.grid(row=0, column=0, columnspan=2, pady=10)

        # --- LEFT COLUMN: Video + Quality ---
        left_frame = tk.Frame(parent_frame)
        left_frame.grid(row=1, column=0, padx=10, pady=10, sticky="n")

        self.video_label = tk.Label(left_frame)
        self.video_label.pack(side=tk.TOP, padx=5)

        # Semaphore + Landmarks Frame (sub-frame inside left)
        sem_land_frame = tk.Frame(left_frame)
        sem_land_frame.pack(side=tk.TOP, pady=10)

        tk.Label(sem_land_frame, text="Calidad", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        self.quality_canvas = tk.Canvas(sem_land_frame, width=130, height=40, bg="#2c2c2c", highlightthickness=0)
        self.quality_canvas.pack(side=tk.LEFT, padx=5)
        self._draw_semaphore('red')

        self.landmarks_var = tk.BooleanVar()
        landmarks_check = tk.Checkbutton(sem_land_frame, text="Malla Facial", variable=self.landmarks_var,
                                         font=("Arial", 9))
        landmarks_check.pack(side=tk.LEFT, padx=15)

        # Camera Selector Frame (below semaphore)
        cam_frame = tk.Frame(left_frame)
        cam_frame.pack(side=tk.TOP, pady=5, fill=tk.X)

        tk.Label(cam_frame, text="📷 Cámara:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        camera_labels = [label for _, label in self.available_cameras] if self.available_cameras else ['No se detectó cámara']
        self.camera_combo = ttk.Combobox(cam_frame, values=camera_labels, state="readonly", width=30)
        self.camera_combo.pack(side=tk.LEFT, padx=5)
        if camera_labels:
            self.camera_combo.current(0)
        self.camera_combo.bind("<<ComboboxSelected>>", self._switch_camera)

        btn_refresh_cam = tk.Button(cam_frame, text="🔄", font=("Arial", 9), command=self._refresh_cameras, width=3)
        btn_refresh_cam.pack(side=tk.LEFT, padx=2)

        # --- RIGHT COLUMN: Form + Config + Monitoring ---
        right_frame = tk.Frame(parent_frame)
        right_frame.grid(row=1, column=1, padx=10, pady=10, sticky="n")

        # 1. Registration Form
        reg_frame = tk.LabelFrame(right_frame, text="Datos del Empleado", font=("Arial", 10, "bold"), padx=10, pady=10)
        reg_frame.pack(fill=tk.X, pady=5)

        tk.Label(reg_frame, text="Nombre:").grid(row=0, column=0, sticky="e", pady=2)
        self.name_entry = tk.Entry(reg_frame, font=("Arial", 10), width=25)
        self.name_entry.grid(row=0, column=1, padx=5, pady=2)

        tk.Label(reg_frame, text="Depto:").grid(row=1, column=0, sticky="e", pady=2)
        self.dept_combo = ttk.Combobox(reg_frame, values=["Ventas", "Operaciones", "IT", "Administración", "Logística", "Otro"], width=22)
        self.dept_combo.grid(row=1, column=1, padx=5, pady=2)
        self.dept_combo.set("Operaciones")

        tk.Label(reg_frame, text="Puesto:").grid(row=2, column=0, sticky="e", pady=2)
        self.pos_combo = ttk.Combobox(reg_frame, values=["Gerente", "Supervisor", "Operador", "Auxiliar", "Otro"], width=22)
        self.pos_combo.grid(row=2, column=1, padx=5, pady=2)
        self.pos_combo.set("Operador")

        tk.Label(reg_frame, text="Turno:").grid(row=3, column=0, sticky="e", pady=2)
        self.shift_combo = ttk.Combobox(reg_frame, values=["Matutino", "Vespertino", "Nocturno"], width=22, state="readonly")
        self.shift_combo.grid(row=3, column=1, padx=5, pady=2)
        self.shift_combo.set("Matutino")

        self.btn_capture = tk.Button(reg_frame, text="📸 Capturar y Registrar", font=("Arial", 11, "bold"), bg="#4CAF50", fg="white", command=self.capture_and_register, state=tk.DISABLED)
        self.btn_capture.grid(row=4, column=0, columnspan=2, pady=10, sticky="ew")

        # 2. Consent & Security
        security_frame = tk.Frame(right_frame)
        security_frame.pack(fill=tk.X, pady=5)

        self.consent_var = tk.BooleanVar()
        self.consent_check = tk.Checkbutton(security_frame, text="Acepto uso de biometría facial", 
                                            variable=self.consent_var, command=self.toggle_capture_btn, font=("Arial", 9))
        self.consent_check.pack(anchor="w")
        
        lbl_privacy = tk.Label(security_frame, text="Ver Aviso de Privacidad", font=("Arial", 9, "underline"), fg="blue", cursor="hand2")
        lbl_privacy.pack(anchor="w")
        lbl_privacy.bind("<Button-1>", self.show_privacy_policy)

        tk.Label(security_frame, text="🔒 Datos cifrados localmente", font=("Arial", 8, "italic"), fg="#4CAF50").pack(anchor="w", pady=5)

        # 3. Management & Config (Grouped)
        tools_frame = tk.LabelFrame(right_frame, text="Herramientas y Gestión", font=("Arial", 10, "bold"), padx=10, pady=10)
        tools_frame.pack(fill=tk.X, pady=5)

        # Delete
        del_sub_frame = tk.Frame(tools_frame)
        del_sub_frame.pack(fill=tk.X, pady=2)
        self.del_employee_combo = ttk.Combobox(del_sub_frame, state="readonly", width=15)
        self.del_employee_combo.pack(side=tk.LEFT, padx=2)
        self._refresh_employee_list(self.del_employee_combo)
        btn_delete = tk.Button(del_sub_frame, text="🗑️ Dar de Baja", bg="#f44336", fg="white", font=("Arial", 8), command=self.delete_employee)
        btn_delete.pack(side=tk.LEFT, padx=5)

        # Calibration
        cal_sub_frame = tk.Frame(tools_frame)
        cal_sub_frame.pack(fill=tk.X, pady=5)
        btn_calibrate = tk.Button(cal_sub_frame, text="📷 Calibrar Fondo", command=self.calibrate_background, bg="#607D8B", fg="white", font=("Arial", 8))
        btn_calibrate.pack(side=tk.LEFT)
        self.lbl_calibration_status = tk.Label(cal_sub_frame, text="Sin calibrar", font=("Arial", 8), fg="grey")
        self.lbl_calibration_status.pack(side=tk.LEFT, padx=5)

        # --- 4. START SYSTEM BUTTON (IMPORTANT) ---
        self.btn_start_system = tk.Button(right_frame, text="🚀 INICIAR MONITOREO", font=("Arial", 14, "bold"), bg="#2196F3", fg="white", command=self.start_system)
        self.btn_start_system.pack(fill=tk.X, pady=15, ipady=10)


    def _build_attendance_tab(self, parent_frame):
        # Filtros Superiores
        filter_frame = tk.Frame(parent_frame)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(filter_frame, text="Desde:").pack(side=tk.LEFT, padx=5)
        self.att_date_from = SelectorDeFecha(filter_frame, inicial=date.today() - timedelta(days=7))
        self.att_date_from.pack(side=tk.LEFT, padx=5)
        
        tk.Label(filter_frame, text="Hasta:").pack(side=tk.LEFT, padx=5)
        self.att_date_to = SelectorDeFecha(filter_frame, inicial=date.today())
        self.att_date_to.pack(side=tk.LEFT, padx=5)
        
        tk.Label(filter_frame, text="Empleado:").pack(side=tk.LEFT, padx=5)
        self.att_employee_combo = ttk.Combobox(filter_frame, state="readonly")
        self.att_employee_combo.pack(side=tk.LEFT, padx=5)
        self._refresh_employee_list(self.att_employee_combo)
        
        btn_generate = tk.Button(filter_frame, text="Generar Reporte", command=self.generate_attendance_report, bg="#4CAF50", fg="white")
        btn_generate.pack(side=tk.LEFT, padx=15)
        
        # Tabla de Datos
        columns = ("Empleado", "Fecha", "Hora Llegada", "Hora Salida", "Horas Totales")
        self.tree_att = ttk.Treeview(parent_frame, columns=columns, show="headings")
        for col in columns:
            self.tree_att.heading(col, text=col)
            self.tree_att.column(col, width=120, anchor=tk.CENTER)
            
        scrollbar = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=self.tree_att.yview)
        self.tree_att.configure(yscroll=scrollbar.set)
        
        self.tree_att.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Acciones Inferiores
        action_frame = tk.Frame(parent_frame)
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        btn_csv = tk.Button(action_frame, text="Exportar a CSV", command=lambda: self.export_to_csv("asistencia"), width=15)
        btn_csv.pack(side=tk.LEFT, padx=5)
        
        btn_pdf = tk.Button(action_frame, text="Exportar a PDF", command=lambda: self.export_to_pdf("asistencia"), width=15)
        btn_pdf.pack(side=tk.LEFT, padx=5)
        
        # Store data for export
        self.current_att_data = []

    def _build_efficiency_tab(self, parent_frame):
        # Filtros Superiores
        filter_frame = tk.Frame(parent_frame)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(filter_frame, text="Desde:").pack(side=tk.LEFT, padx=5)
        self.eff_date_from = SelectorDeFecha(filter_frame, inicial=date.today() - timedelta(days=7))
        self.eff_date_from.pack(side=tk.LEFT, padx=5)
        
        tk.Label(filter_frame, text="Hasta:").pack(side=tk.LEFT, padx=5)
        self.eff_date_to = SelectorDeFecha(filter_frame, inicial=date.today())
        self.eff_date_to.pack(side=tk.LEFT, padx=5)
        
        tk.Label(filter_frame, text="Empleado:").pack(side=tk.LEFT, padx=5)
        self.eff_employee_combo = ttk.Combobox(filter_frame, state="readonly")
        self.eff_employee_combo.pack(side=tk.LEFT, padx=5)
        self._refresh_employee_list(self.eff_employee_combo)
        
        btn_generate = tk.Button(filter_frame, text="Generar Reporte", command=self.generate_efficiency_report, bg="#4CAF50", fg="white")
        btn_generate.pack(side=tk.LEFT, padx=15)
        
        # Tabla de Datos
        columns = ("Empleado", "Fecha", "Tiempo Total", "Tiempo Activo (Zonas)", "% Eficiencia")
        self.tree_eff = ttk.Treeview(parent_frame, columns=columns, show="headings")
        for col in columns:
            self.tree_eff.heading(col, text=col)
            self.tree_eff.column(col, width=120, anchor=tk.CENTER)
            
        scrollbar = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=self.tree_eff.yview)
        self.tree_eff.configure(yscroll=scrollbar.set)
        
        self.tree_eff.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Acciones Inferiores
        action_frame = tk.Frame(parent_frame)
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        btn_csv = tk.Button(action_frame, text="Exportar a CSV", command=lambda: self.export_to_csv("eficiencia"), width=15)
        btn_csv.pack(side=tk.LEFT, padx=5)
        
        btn_pdf = tk.Button(action_frame, text="Exportar a PDF", command=lambda: self.export_to_pdf("eficiencia"), width=15)
        btn_pdf.pack(side=tk.LEFT, padx=5)

        btn_reveal = tk.Button(action_frame, text="👁 Revelar Identidades", command=self.unlock_admin_view)
        btn_reveal.pack(side=tk.LEFT, padx=15)
        
        self.current_eff_data = []

        # Double-click on efficiency row to view snapshot
        self.tree_eff.bind('<Double-1>', self.on_efficiency_row_dblclick)

    def _refresh_employee_list(self, combo_widget):
        employees = self.db.get_unique_employees()
        # Filter out pseudo-anonymized names
        employees = [emp for emp in employees if not emp.startswith("empleado_eliminado_")]
        
        values = ["Todos"] + employees
        
        # Keep old selection if possible, otherwise default to "Todos"
        current_selection = combo_widget.get()
        combo_widget['values'] = values
        
        if current_selection in values:
            combo_widget.set(current_selection)
        else:
            combo_widget.current(0)
            
    def delete_employee(self):
        name = self.del_employee_combo.get()
        if not name or name == "Todos":
            messagebox.showwarning("Advertencia", "Por favor selecciona un empleado válido para dar de baja.")
            return

        confirm = messagebox.askyesno(
            "Confirmación Crítica", 
            f"¿Estás seguro de que deseas dar de baja y eliminar los datos biométricos de '{name}'?\n\nEsta acción es irreversible.", 
            icon='warning')
            
        if confirm:
            try:
                # 1. Eliminar datos físicos y encodings (FaceRecognizer)
                self.face_recognizer.delete_face(name)
                
                # 2. Anonimizar en base de datos (Derecho al olvido)
                self.db.anonymize_employee(name)
                
                # 3. Eliminar perfil de la tabla employees para permitir re-registro
                self.db.delete_employee_profile(name)
                
                # 4. Refrescar todas las listas desplegables
                self._refresh_employee_list(self.att_employee_combo)
                self._refresh_employee_list(self.eff_employee_combo)
                self._refresh_employee_list(self.del_employee_combo)
                
                messagebox.showinfo("Éxito", f"El empleado '{name}' ha sido dado de baja correctamente. Sus datos personales han sido eliminados.")
            except Exception as e:
                messagebox.showerror("Error", f"Ocurrió un error al intentar eliminar al empleado: {e}")

    def _consultar_reporte(self, desde, hasta, empleado, consulta):
        """Filas del reporte, o None si el rango es inválido (se avisa y no se consulta)."""
        try:
            return consultar_reporte(desde.get(), hasta.get(), empleado.get(), consulta)
        except (FechaInvalidaError, RangoDeFechasInvalidoError) as error:
            messagebox.showerror("Rango de fechas inválido", str(error))
            return None

    def generate_attendance_report(self):
        data = self._consultar_reporte(self.att_date_from, self.att_date_to,
                                       self.att_employee_combo, self.db.get_attendance_report)
        if data is None:
            return

        # Clear tree
        for item in self.tree_att.get_children():
            self.tree_att.delete(item)

        self.current_att_data = data
        
        for row in data:
            self.tree_att.insert("", tk.END, values=row)
            
    def generate_efficiency_report(self):
        data = self._consultar_reporte(self.eff_date_from, self.eff_date_to,
                                       self.eff_employee_combo, self.db.get_efficiency_report)
        if data is None:
            return

        # Clear tree
        for item in self.tree_eff.get_children():
            self.tree_eff.delete(item)

        self.current_eff_data = data
        
        for row in data:
            self.tree_eff.insert("", tk.END, values=row)

    def export_to_csv(self, report_type):
        if report_type == "asistencia":
            data = self.current_att_data
            columns = ["Empleado", "Fecha", "Hora Llegada", "Hora Salida", "Horas Totales"]
            default_name = f"Reporte_Asistencia_{datetime.now().strftime('%Y%m%d')}.csv"
        else:
            data = self.current_eff_data
            columns = ["Empleado", "Fecha", "Tiempo Total", "Tiempo Activo (Zonas)", "% Eficiencia"]
            default_name = f"Reporte_Eficiencia_{datetime.now().strftime('%Y%m%d')}.csv"
            
        if not data:
            messagebox.showwarning("Advertencia", "No hay datos para exportar. Genera el reporte primero.")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        
        if filepath:
            try:
                df = pd.DataFrame(data, columns=columns)
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
                messagebox.showinfo("Éxito", f"Reporte exportado correctamente a:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al exportar a CSV: {e}")

    def export_to_pdf(self, report_type):
        if report_type == "asistencia":
            data = self.current_att_data
            columns = ["Empleado", "Fecha", "Llegada", "Salida", "Horas"]
            default_name = f"Reporte_Asistencia_{datetime.now().strftime('%Y%m%d')}.pdf"
            title = "Reporte de Asistencia"
        else:
            data = self.current_eff_data
            columns = ["Empleado", "Fecha", "T. Total", "T. Activo", "% Eficiencia"]
            default_name = f"Reporte_Eficiencia_{datetime.now().strftime('%Y%m%d')}.pdf"
            title = "Reporte de Eficiencia"
            
        if not data:
            messagebox.showwarning("Advertencia", "No hay datos para exportar. Genera el reporte primero.")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*")]
        )
        
        if filepath:
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.lib import colors
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet
                
                doc = SimpleDocTemplate(filepath, pagesize=letter)
                elements = []
                styles = getSampleStyleSheet()
                
                # Title
                elements.append(Paragraph(title, styles['Title']))
                elements.append(Spacer(1, 12))
                
                # Table Data
                table_data = [columns] + list(data)
                
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,0), 12),
                    ('BOTTOMPADDING', (0,0), (-1,0), 12),
                    ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                ]))
                
                elements.append(t)
                doc.build(elements)
                
                messagebox.showinfo("Éxito", f"Reporte exportado correctamente a:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al exportar a PDF: {e}")


    def _update_video(self):
        import time as _time
        if hasattr(self, 'cap') and self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame.copy()
                display = cv2.resize(frame, (640, 480))

                # --- Background Subtraction (Demo/MVP Noise Reduction) ---
                if self.bg_subtractor is not None:
                    # Apply subtractor to 'clean' the mask (learningRate=0 to keep static ref)
                    mask = self.bg_subtractor.apply(display, learningRate=0)
                    # We could use this mask to black out background, but for now just show we are 'processing'
                    # display = cv2.bitwise_and(display, display, mask=mask) # Optional: uncomment if hard subtraction is desired
                    pass

                # --- Face detection (Haar Cascade) ---
                gray = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(80, 80))

                self.detected_face_rect = None
                if len(faces) > 0:
                    # Take largest face
                    largest = max(faces, key=lambda r: r[2] * r[3])
                    fx, fy, fw, fh = largest
                    self.detected_face_rect = (fx, fy, fw, fh)

                    # Draw bounding box
                    cv2.rectangle(display, (fx, fy), (fx + fw, fy + fh), (255, 180, 0), 2)

                    # --- Quality calculation ---
                    face_roi_gray = gray[fy:fy+fh, fx:fx+fw]
                    mean_brightness = face_roi_gray.mean()
                    h_frame, w_frame = display.shape[:2]
                    face_cx = fx + fw // 2
                    face_cy = fy + fh // 2
                    center_zone_x = (w_frame * 0.35, w_frame * 0.65)
                    center_zone_y = (h_frame * 0.25, h_frame * 0.75)
                    is_centered = (center_zone_x[0] <= face_cx <= center_zone_x[1] and
                                   center_zone_y[0] <= face_cy <= center_zone_y[1])
                    face_area_ratio = (fw * fh) / (w_frame * h_frame)

                    if 60 < mean_brightness < 200 and is_centered and face_area_ratio > 0.03:
                        self.quality_state = 'green'
                    elif 40 < mean_brightness < 220 and len(faces) > 0:
                        self.quality_state = 'yellow'
                    else:
                        self.quality_state = 'red'

                    # --- Liveness: motion detection between consecutive face crops ---
                    if self.prev_gray_face is not None and self.prev_gray_face.shape == face_roi_gray.shape:
                        diff = cv2.absdiff(self.prev_gray_face, face_roi_gray)
                        motion_score = diff.mean()
                        if motion_score > 1.5:
                            self.liveness_confirmed = True
                    self.prev_gray_face = face_roi_gray.copy()

                    # Draw liveness indicator
                    if self.liveness_confirmed:
                        cv2.putText(display, "Persona real detectada", (fx, fy - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 2)
                    else:
                        cv2.putText(display, "Esperando movimiento...", (fx, fy - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 180, 255), 1)

                    # --- Landmarks (Demo Mode) ---
                    if self.landmarks_var.get():
                        try:
                            display_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
                            # Optimize by providing the pre-computed bounding box from Haar cascade
                            # face_recognition takes (top, right, bottom, left) format
                            face_locs = [(fy, fx + fw, fy + fh, fx)]
                            landmarks_list = face_recognition.face_landmarks(display_rgb, face_locations=face_locs)
                            for landmarks in landmarks_list:
                                for feature_name, points in landmarks.items():
                                    # Puntos más pequeños y de color celeste neón
                                    for point in points:
                                        cv2.circle(display, point, 2, (255, 200, 50), -1) 
                                    
                                    # Líneas conectando los puntos para formar la malla
                                    pts = list(points)
                                    for j in range(len(pts) - 1):
                                        cv2.line(display, pts[j], pts[j+1], (255, 200, 50), 1)
                                        
                                    # Para polígonos cerrados como ojos y labios, conectar el último con el primero
                                    if feature_name in ['left_eye', 'right_eye', 'top_lip', 'bottom_lip'] and len(pts) > 0:
                                        cv2.line(display, pts[-1], pts[0], (255, 200, 50), 1)
                        except Exception as e:
                            print(f"Error drawing landmarks: {e}")
                else:
                    self.quality_state = 'red'
                    self.liveness_confirmed = False
                    self.prev_gray_face = None

                # Update quality semaphore UI
                if hasattr(self, 'quality_canvas'):
                    self._draw_semaphore(self.quality_state)

                # --- Countdown overlay ---
                if self.countdown_value > 0:
                    txt = str(self.countdown_value)
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    scale = 4.0
                    thickness = 8
                    (tw, th), _ = cv2.getTextSize(txt, font, scale, thickness)
                    cx = (display.shape[1] - tw) // 2
                    cy = (display.shape[0] + th) // 2
                    # Semi-transparent background
                    overlay = display.copy()
                    cv2.rectangle(overlay, (cx - 20, cy - th - 20), (cx + tw + 20, cy + 20), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.4, display, 0.6, 0, display)
                    cv2.putText(display, txt, (cx, cy), font, scale, (255, 255, 255), thickness)

                # --- Tint overlay (success/error) ---
                if self.tint_color and _time.time() < self.tint_until:
                    border = 12
                    color = (0, 200, 0) if self.tint_color == 'green' else (0, 0, 220)
                    cv2.rectangle(display, (0, 0), (display.shape[1]-1, display.shape[0]-1), color, border)
                elif self.tint_color:
                    self.tint_color = None

                # Convert BGR to RGB for Tkinter
                cv_image = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(cv_image)
                imgtk = ImageTk.PhotoImage(image=pil_image)
                
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)
        
        self.root.after(30, self._update_video)

    def capture_and_register(self):
        """Inicia la secuencia de cuenta regresiva y captura en ráfaga."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Advertencia", "Por favor ingresa el nombre del empleado.")
            return

        if self.current_frame is None:
            messagebox.showerror("Error", "No hay imagen de la cámara.")
            return

        if self.quality_state == 'red':
            messagebox.showwarning("Calidad Insuficiente", "La calidad de la imagen es demasiado baja. Asegúrate de que el rostro esté bien iluminado y centrado.")
            return

        # Duplicate prevention: check filesystem and database
        person_dir = os.path.join(self.faces_dir, name)
        if os.path.exists(person_dir) or self.db.employee_exists(name):
            messagebox.showwarning("Empleado Duplicado",
                f"El empleado \"{name}\" ya se encuentra registrado.\n\n"
                "Por favor, usa un nombre distinto o elimina el registro anterior desde la sección 'Gestión de Empleados'.")
            return

        # Lock UI and start countdown
        self.is_capturing = True
        self.btn_capture.config(state=tk.DISABLED, text="Preparando...")
        self.burst_frames = []
        self.countdown_value = 3
        self._run_countdown()

    def _run_countdown(self):
        """Ejecuta la cuenta regresiva de 3..2..1 y luego captura en ráfaga."""
        if self.countdown_value > 0:
            self.btn_capture.config(text=f"  {self.countdown_value}...  ")
            self.countdown_value -= 1
            self.root.after(1000, self._run_countdown)
        else:
            self.countdown_value = 0
            self.btn_capture.config(text="📸 Capturando...")
            self.root.after(200, self._collect_burst)

    def _collect_burst(self):
        """Captura 5 frames espaciados por 300ms."""
        if self.current_frame is not None:
            self.burst_frames.append(self.current_frame.copy())
        
        if len(self.burst_frames) < 5:
            self.root.after(300, self._collect_burst)
        else:
            self._process_burst()

    def _process_burst(self):
        """Procesa los frames capturados en ráfaga."""
        import time
        name = self.name_entry.get().strip()
        department = self.dept_combo.get()
        position = self.pos_combo.get()
        shift = self.shift_combo.get()

        # Liveness check: verify frames are not static (anti-spoofing)
        if len(self.burst_frames) >= 2:
            import numpy as np
            diffs = []
            for i in range(len(self.burst_frames) - 1):
                g1 = cv2.cvtColor(self.burst_frames[i], cv2.COLOR_BGR2GRAY).astype(float)
                g2 = cv2.cvtColor(self.burst_frames[i+1], cv2.COLOR_BGR2GRAY).astype(float)
                # Resize to same shape to be safe
                g2 = cv2.resize(g2, (g1.shape[1], g1.shape[0]))
                diffs.append(cv2.absdiff(g1, g2).mean())
            avg_motion = sum(diffs) / len(diffs)
            if avg_motion < 1.0:
                self.tint_color = 'red'
                self.tint_until = time.time() + 2.0
                messagebox.showwarning("Liveness Fallido", "Se detectó una imagen estática. Asegúrate de que es una persona real frente a la cámara.")
                self._reset_capture_state()
                return

        # Save burst frames to temp files (use system temp dir to avoid path issues in .exe)
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_paths = []
        for i, frame in enumerate(self.burst_frames):
            ts = time.strftime("%Y%m%d_%H%M%S")
            temp_path = os.path.join(temp_dir, f"temp_burst_{ts}_{i}.jpg")
            write_ok = cv2.imwrite(temp_path, frame)
            if write_ok and os.path.exists(temp_path):
                temp_paths.append(temp_path)
                print(f"  Burst frame {i} saved: {temp_path} ({os.path.getsize(temp_path)} bytes)")
            else:
                print(f"  ⚠️ Failed to save burst frame {i} to {temp_path}")
        
        if not temp_paths:
            self.tint_color = 'red'
            self.tint_until = time.time() + 2.0
            messagebox.showerror("Error", "No se pudieron guardar las capturas temporales.")
            self._reset_capture_state()
            return
        
        try:
            success_count = self.face_recognizer.register_face_burst(temp_paths, name)
            if success_count > 0:
                self.db.save_employee_profile(name, department, position, shift)
                self.tint_color = 'green'
                self.tint_until = time.time() + 2.0
                messagebox.showinfo("Éxito", f"Empleado {name} registrado con {success_count} capturas exitosas.")
                self.name_entry.delete(0, tk.END)
            else:
                self.tint_color = 'red'
                self.tint_until = time.time() + 2.0
                messagebox.showerror("Error", "No se detectó un rostro en ninguna de las capturas.")
        except Exception as e:
            self.tint_color = 'red'
            self.tint_until = time.time() + 2.0
            error_msg = "El rostro no pudo guardarse" if "same file" in str(e).lower() else str(e)
            messagebox.showerror("Error Fatal", f"Ocurrió un error al registrar: {error_msg}")
        finally:
            for tp in temp_paths:
                if os.path.exists(tp):
                    os.remove(tp)
            self._reset_capture_state()

    def _reset_capture_state(self):
        """Restaura la interfaz después de la captura."""
        self.is_capturing = False
        self.burst_frames = []
        self.countdown_value = 0
        self.liveness_confirmed = False
        self.prev_gray_face = None
        self.btn_capture.config(state=tk.NORMAL, text="📸 Capturar y Registrar")
        self.consent_var.set(False)
        self.toggle_capture_btn()

    def toggle_capture_btn(self):
        """Habilita el botón solo si: consentimiento marcado + calidad verde + liveness OK."""
        if self.is_capturing:
            return  # Don't toggle during capture sequence
        consent = self.consent_var.get()
        quality_ok = self.quality_state in ('green', 'yellow')
        if consent and quality_ok:
            self.btn_capture.config(state=tk.NORMAL)
        else:
            self.btn_capture.config(state=tk.DISABLED)

    def _draw_semaphore(self, state):
        """Dibuja el semáforo de calidad (3 círculos en el Canvas)."""
        c = self.quality_canvas
        c.delete('all')
        colors = {
            'red':    ('#ff3333', '#552222', '#552222'),
            'yellow': ('#552222', '#ffcc00', '#552222'),
            'green':  ('#552222', '#552222', '#33cc33'),
        }
        r_col, y_col, g_col = colors.get(state, colors['red'])
        c.create_oval(5, 5, 35, 35, fill=r_col, outline='#333')
        c.create_oval(45, 5, 75, 35, fill=y_col, outline='#333')
        c.create_oval(85, 5, 115, 35, fill=g_col, outline='#333')

    def calibrate_background(self):
        """Captura el frame actual como referencia de fondo vacío."""
        import time
        if self.current_frame is None:
            messagebox.showerror("Error", "No hay imagen de la cámara para calibrar.")
            return

        try:
            # Save reference in memory
            self.background_reference = self.current_frame.copy()
            
            # Initialize MOG2 Subtractor
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)
            # Pre-train with the background frame (learning rate 1.0 to set it as baseline)
            self.bg_subtractor.apply(self.background_reference, learningRate=1.0)

            # Save to disk
            try:
                from config.config import CALIBRATION_DIR
                config_dir = CALIBRATION_DIR
            except ImportError:
                config_dir = os.path.join("data", "config")
                os.makedirs(config_dir, exist_ok=True)
            bg_path = os.path.join(config_dir, "bg_ref.jpg")
            cv2.imwrite(bg_path, self.background_reference)

            self.lbl_calibration_status.config(text="Calibrado ✅", fg="#4CAF50")
            
            # Flash effect
            self.tint_color = 'green'
            self.tint_until = time.time() + 1.0
            
            messagebox.showinfo("Éxito", "Fondo calibrado exitosamente. El sistema ahora filtrará mejor el ruido estático.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo calibrar el fondo: {e}")

    def show_privacy_policy(self, event=None):
        policy_text = (
            "Aviso de Privacidad Simplificado\n\n"
            "Conforme a las normativas vigentes sobre protección de datos personales y privacidad:\n\n"
            "1. Los datos biométricos (fotografías y mediciones faciales) capturados por este sistema "
            "tienen como única finalidad el registro y control de asistencia, así como la medición "
            "de métricas de eficiencia en su respectiva área de trabajo.\n\n"
            "2. La información es almacenada y cifrada de forma local. No se comparte ni se transfiere "
            "a terceros ajenos a la administración de esta empresa.\n\n"
            "3. En caso de baja del empleado, los datos biométricos (rostros) podrán ser eliminados "
            "permanentemente del sistema para garantizar el derecho al olvido, preservando únicamente "
            "las estadísticas anónimas de eficiencia.\n\n"
            "Al marcar la casilla de consentimiento, usted acepta el tratamiento de su información "
            "conforme a las finalidades descritas."
        )
        messagebox.showinfo("Aviso de Privacidad", policy_text)

    def on_efficiency_row_dblclick(self, event):
        """Al hacer doble clic en una fila de eficiencia, abre el visor de snapshots."""
        selected = self.tree_eff.selection()
        if not selected:
            return
        values = self.tree_eff.item(selected[0], 'values')
        if not values:
            return
        employee_name = values[0]  # Columna "Empleado"
        date_str = values[1]       # Columna "Fecha"
        
        snapshots = self.db.get_employee_snapshots(employee_name, date_str)
        if not snapshots:
            messagebox.showinfo("Sin Snapshots", f"No hay capturas registradas para {employee_name} en {date_str}.")
            return
        
        self.show_snapshot_viewer(employee_name, date_str, snapshots)

    def show_snapshot_viewer(self, employee_name, date_str, snapshot_paths):
        """Abre una ventana Toplevel con los snapshots. Si el admin NO está desbloqueado, se aplica desenfoque."""
        viewer = tk.Toplevel(self.root)
        viewer.title(f"Snapshots - {employee_name} ({date_str})")
        viewer.geometry("700x500")
        
        canvas_frame = tk.Frame(viewer)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable = tk.Frame(canvas)
        
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Store references to prevent garbage collection
        viewer._photo_refs = []
        
        for path in snapshot_paths:
            if not os.path.exists(path):
                continue
            try:
                img = cv2.imread(path)
                if img is None:
                    continue
                    
                # Apply blur if admin is NOT unlocked
                if not self.is_admin_unlocked:
                    img = cv2.GaussianBlur(img, (99, 99), 30)
                
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                # Resize for display
                h, w = img_rgb.shape[:2]
                max_w = 640
                if w > max_w:
                    scale = max_w / w
                    img_rgb = cv2.resize(img_rgb, (max_w, int(h * scale)))
                
                pil_img = Image.fromarray(img_rgb)
                photo = ImageTk.PhotoImage(pil_img)
                viewer._photo_refs.append(photo)
                
                lbl = tk.Label(scrollable, image=photo)
                lbl.pack(pady=5)
                
                caption = tk.Label(scrollable, text=os.path.basename(path), font=("Arial", 8), fg="grey")
                caption.pack()
            except Exception as e:
                print(f"Error loading snapshot {path}: {e}")
        
        if not viewer._photo_refs:
            tk.Label(scrollable, text="No se pudieron cargar las imágenes.", font=("Arial", 12)).pack(pady=20)

    def unlock_admin_view(self):
        """Solicita la contraseña de administrador para revelar identidades en los snapshots."""
        import hashlib
        password = simpledialog.askstring("Autenticación", "Ingresa la contraseña de administrador:", show='*')
        if password is None:
            return
        
        entered_hash = hashlib.sha256(password.encode()).hexdigest()
        if entered_hash == self.ADMIN_PASSWORD_HASH:
            self.is_admin_unlocked = True
            messagebox.showinfo("Acceso Concedido", "Identidades desbloqueadas para esta sesión. Los snapshots se mostrarán sin filtro.")
        else:
            messagebox.showerror("Acceso Denegado", "Contraseña incorrecta.")

    def start_system(self):
        # We start the main monitoring system in the same process
        # because PyInstaller (subprocess sys.executable) will just relaunch the GUI app infinitely.
        if messagebox.askyesno("Confirmar", "¿Deseas iniciar el monitoreo principal? Esto cerrará la ventana de registro."):
            # Pass selected camera to main.py via env var
            if self.selected_camera_index is not None:
                os.environ['SELECTED_CAMERA_INDEX'] = str(self.selected_camera_index)
            self._close_camera()
            self.root.destroy()
            
            try:
                from src import main
                main.start_video_stream()
            except Exception as e:
                print(f"Error al iniciar el sistema principal: {e}")

    def _close_camera(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

    def on_close(self):
        self._close_camera()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SystemGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
