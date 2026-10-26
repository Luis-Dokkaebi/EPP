import queue

import customtkinter as ctk

# Configuracion global de tema segun 1_SPECIFICATIONS.md
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Cada cuánto el hilo de la UI revisa si el escaneo de cámaras (hilo de fondo) terminó.
INTERVALO_SONDEO_ESCANEO_MS = 100
# Sin filtro extra: Ultralytics ya aplica su umbral interno (0.25), como antes de usar el puerto.
CONFIANZA_MINIMA_GUI = 0.0

class ViewManager:
    """Clase singleton-like para manejar el renderizado condicional de vistas (caching de frames)."""
    def __init__(self, main_workspace: ctk.CTkFrame):
        self.workspace = main_workspace
        self.current_view = None
        self.views = {}

    def register_view(self, name: str, view_instance: ctk.CTkFrame):
        self.views[name] = view_instance

    def switch_to(self, name: str):
        if self.current_view is not None:
            self.current_view.pack_forget()
        
        if name not in self.views:
            return
            
        view_instance = self.views[name]
        view_instance.pack(fill="both", expand=True, padx=20, pady=20)
        self.current_view = view_instance

class AppMain(ctk.CTk):
    def __init__(self, licencia=None):
        super().__init__()

        # SPEC/9 §5.4 y D10: la licencia validada decide si las cámaras suman el módulo de EPP;
        # el publicador lleva sus infracciones a la interfaz.
        from src.composicion_epp import PublicadorEnMemoria
        self.licencia = licencia
        self.publicador_epp = PublicadorEnMemoria()
        self._despachador_epp = self._iniciar_avisos_epp()
        
        self.title("Oficina Eficiencia B2B")
        self.geometry("1400x800")
        self.configure(fg_color="#1E1E1E")
        self.minsize(1024, 768)
        
        # Estado de cámaras detectadas
        self._detected_cameras = []
        self._active_camera_index = None
        
        # Grid System for Root (1 Row, 2 Columns)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0)
        
        # --- SIDEBAR ---
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color="#2B2B2B", border_width=1, border_color="#333333")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="VMS Panel", font=("Roboto", 24, "bold"), text_color="#FFFFFF")
        self.logo_label.pack(pady=(30, 15), padx=20, anchor="w")
        
        # --- MAIN WORKSPACE ---
        self.main_workspace = ctk.CTkFrame(self, corner_radius=0, fg_color="#1E1E1E")
        self.main_workspace.grid(row=0, column=1, sticky="nsew")
        
        # --- VIEW MANAGER ---
        self.view_manager = ViewManager(self.main_workspace)
        self.setup_views()
        self.setup_sidebar_buttons()
        self._build_camera_selector()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.view_manager.switch_to("Dashboard")
        
        # Escanear cámaras de forma asíncrona al iniciar
        self._scan_cameras()
        
    def setup_views(self):
        """Inicializa las vistas con lógica de negocio REAL."""
        import queue
        from src.gui.dashboard import DashboardFrame
        from src.gui.views import create_employees_view, create_zones_view, create_reports_view, create_tenant_view
        
        self.camera_workers = []
        self.camera_queues = {}
        
        # CR-05: el parche de torch.load vive confinado en la raíz de composición (A-15).
        try:
            from src.composition import crear_detector_configurado

            detector = crear_detector_configurado(CONFIANZA_MINIMA_GUI)

        except Exception as e:
            print(f"[VMS] No se pudo cargar YOLO: {e}")
            import tkinter.messagebox
            tkinter.messagebox.showerror("Error Crítico de IA", f"No se pudo cargar el motor YOLO B2B:\n\n{e}\n\nFavor de reportar este problema.")
            detector = None
        
        self.detector = detector
        self.view_dashboard = DashboardFrame(self.main_workspace, self.camera_queues)
        self.view_manager.register_view("Dashboard", self.view_dashboard)
        
        self.view_empleados = create_employees_view(self, self.main_workspace)
        self.view_manager.register_view("Empleados", self.view_empleados)
        
        self.view_zonas = create_zones_view(self.main_workspace)
        self.view_manager.register_view("Zonas", self.view_zonas)
        
        self._registrar_vistas_epp()

        self.view_reportes = create_reports_view(self.main_workspace)
        self.view_manager.register_view("Reportes", self.view_reportes)
        
        self.view_manager.register_view("Tenant", create_tenant_view(self.main_workspace))

    def _start_local_camera(self, camera_index=None):
        import queue
        from config.config import LOCAL_CAMERA_INDEX
        from src.tracking.camera_worker import CameraWorker
        if self.detector is None: return
        
        idx = camera_index if camera_index is not None else LOCAL_CAMERA_INDEX
        self._active_camera_index = idx
        
        cam_name = "Cámara Local"
        if cam_name not in self.camera_queues:
            self.camera_queues[cam_name] = queue.Queue(maxsize=10)
            self.view_dashboard.camera_queues = self.camera_queues
            self.view_dashboard.setup_grid()
        q = self.camera_queues[cam_name]
        worker = CameraWorker(idx, q, self.detector, fps_limit=15)
        self._conectar_epp(worker)
        worker.start()
        self.camera_workers.append(worker)
        
        if hasattr(self, '_cam_status_label'):
            self._cam_status_label.configure(
                text=f"✅ Activa: índice {idx}",
                text_color="#2ECC71"
            )

    def _conectar_epp(self, worker):
        """Cada cámara lleva su propio módulo de EPP (estado por track), si la licencia lo habilita."""
        if self.licencia is None:
            return
        from src import composicion_epp
        worker.conectar_epp(
            composicion_epp.crear_integracion_epp_de_la_app(self.publicador_epp, self.licencia))

    def _stop_local_camera(self):
        # CR-09: NO dormir en el hilo de UI. Los workers son daemon y sueltan el
        # dispositivo por su cuenta; bloquear con time.sleep congelaba CustomTkinter
        # 500ms (ventana "No responde") y habilitaba dobles-clic que creaban workers
        # duplicados. El reinicio se reprograma con .after en _switch_camera.
        for w in self.camera_workers:
            w.stop()
        self.camera_workers.clear()

    def _modulo_epp_habilitado(self):
        from src.composicion_epp import modulo_habilitado
        return modulo_habilitado(self.licencia)

    def _registrar_vistas_epp(self):
        """SPEC/9 §8.2 y §8.4: alertas y reporte de cumplimiento, solo con el módulo de EPP."""
        if self._modulo_epp_habilitado():
            from src.gui import epp_en_la_app
            epp_en_la_app.registrar_vistas(self.view_manager, self.main_workspace)

    def _iniciar_avisos_epp(self):
        """SPEC/9 §5.4: los avisos de EPP arrancan solo si la licencia incluye el módulo."""
        if not self._modulo_epp_habilitado():
            return None
        from src.composicion_avisos import iniciar_avisos_de_la_sucursal
        return iniciar_avisos_de_la_sucursal()

    def on_closing(self):
        for w in self.camera_workers:
            w.stop()
        if self._despachador_epp is not None:
            # Antes de destruir la ventana: main() cifra la base al volver de mainloop.
            from datetime import timedelta
            self._despachador_epp.detener(timedelta(seconds=10))
        self.destroy()

    def setup_sidebar_buttons(self):
        buttons = [
            ("Monitoreo en Vivo", "Dashboard"),
            ("Gestión de Empleados", "Empleados"),
            ("Configuración de Zonas", "Zonas"),
            ("Reportes Históricos", "Reportes"),
            ("Cambiar Sucursal", "Tenant")
        ]
        if self._modulo_epp_habilitado():
            buttons[3:3] = [("Alertas EPP", "AlertasEPP"), ("Cumplimiento EPP", "CumplimientoEPP")]
        
        for text, view_name in buttons:
            btn = ctk.CTkButton(
                self.sidebar_frame, text=text, font=("Roboto", 14),
                fg_color="#1f6aa5", hover_color="#144870",
                text_color="#FFFFFF", corner_radius=8, height=40, anchor="w",
                command=lambda name=view_name: self.view_manager.switch_to(name)
            )
            btn.pack(pady=5, padx=20, fill="x")

    def _build_camera_selector(self):
        from src.gui.views import build_camera_selector
        build_camera_selector(self, self.sidebar_frame)
    
    def _scan_cameras(self) -> None:
        from src.acquisition.camera_enumerator import enumerate_cameras_async
        
        self._cam_status_label.configure(text="⏳ Escaneando...", text_color="#F39C12")
        self._cam_combo.configure(values=["Escaneando..."])
        self._cam_combo.set("Escaneando...")

        # Tk solo se usa desde su hilo: el escaneo deja el resultado en una cola y la UI la
        # sondea con after(). Llamar a Tk desde el hilo de fondo usaba el intérprete Tcl desde
        # dos hilos a la vez (Segmentation fault / Illegal instruction intermitentes).
        resultado_escaneo: queue.Queue[list[dict]] = queue.Queue()
        enumerate_cameras_async(resultado_escaneo.put, max_index=10)
        self._recibir_escaneo(resultado_escaneo)

    def _recibir_escaneo(self, resultado_escaneo: queue.Queue[list[dict]]) -> None:
        try:
            cameras = resultado_escaneo.get_nowait()
        except queue.Empty:
            self.after(INTERVALO_SONDEO_ESCANEO_MS, self._recibir_escaneo, resultado_escaneo)
            return
        self._detected_cameras = cameras
        self._update_camera_list(cameras)

    def _update_camera_list(self, cameras):
        if cameras:
            labels = [cam["label"] for cam in cameras]
            self._cam_combo.configure(values=labels)
            self._cam_combo.set(labels[0])
            self._cam_status_label.configure(
                text=f"🔍 {len(cameras)} cámara(s) detectada(s)",
                text_color="#2ECC71"
            )
            if self._active_camera_index is None:
                self._on_camera_selected()
        else:
            self._cam_combo.configure(values=["Sin cámaras detectadas"])
            self._cam_combo.set("Sin cámaras detectadas")
            self._cam_status_label.configure(
                text="❌ No se detectaron cámaras",
                text_color="#E74C3C"
            )
    
    def _on_camera_selected(self):
        selected = self._cam_combo.get()
        if selected in ("Escaneando...", "Sin cámaras detectadas"):
            return
        
        cam_index = None
        for cam in self._detected_cameras:
            if cam["label"] == selected:
                cam_index = cam["index"]
                break
        
        if cam_index is None:
            return
        
        self._switch_camera(cam_index)
    
    def _on_manual_camera(self):
        val = self._cam_manual_entry.get().strip()
        if not val:
            self._cam_status_label.configure(text="⚠️ Ingrese un índice", text_color="#E74C3C")
            return
        
        if val.startswith("rtsp://") or val.startswith("http://"):
            cam_id = val
        else:
            try:
                cam_id = int(val)
            except ValueError:
                self._cam_status_label.configure(text="⚠️ Índice inválido", text_color="#E74C3C")
                return
        
        self._switch_camera(cam_id)
    
    def _switch_camera(self, camera_id):
        self._cam_status_label.configure(text="⏳ Conectando...", text_color="#F39C12")
        # CR-09: deshabilitar "Conectar" mientras hay un cambio en curso evita el
        # doble-clic que crea CameraWorkers duplicados compitiendo por la cámara.
        if hasattr(self, '_cam_connect_btn'):
            self._cam_connect_btn.configure(state="disabled")
        self.update_idletasks()

        self._stop_local_camera()
        self.camera_queues.clear()
        # No bloquear el hilo de UI: reprogramar el arranque con .after para dar
        # tiempo a que el worker daemon libere el dispositivo.
        self.after(500, lambda: self._finish_switch_camera(camera_id))

    def _finish_switch_camera(self, camera_id):
        self._start_local_camera(camera_index=camera_id)
        if hasattr(self, '_cam_connect_btn'):
            self._cam_connect_btn.configure(state="normal")

import os
from config.path_utils import ConfigManager
from src.security.drm import DRMValidator

class LicenseWindow(ctk.CTkToplevel):
    def __init__(self, master, drm_validator):
        super().__init__(master)
        self.title("Activación Corporativa B2B (DRM RSA-2048)")
        self.geometry("620x520")
        self.configure(fg_color="#1E1E1E")
        self.attributes("-topmost", True)
        self.grab_set()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.drm = drm_validator
        self.activated = False
        
        ctk.CTkLabel(self, text="🔐 Licencia Requerida", font=("Roboto", 22, "bold"), text_color="#E74C3C").pack(pady=(15, 5))
        ctk.CTkLabel(self, text="Envíe el siguiente Machine ID a su proveedor para recibir la llave:", 
                     font=("Roboto", 12), text_color="#A0A0A0").pack(pady=5)
        
        mid_frame = ctk.CTkFrame(self, fg_color="#2B2B2B", corner_radius=8)
        mid_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(mid_frame, text="Machine ID (SHA-256 Hardware Fingerprint):", 
                     font=("Roboto", 11), text_color="#A0A0A0").pack(pady=(8, 2), padx=10, anchor="w")
        
        self.mid_entry = ctk.CTkEntry(mid_frame, justify="center", font=("Consolas", 11), height=32)
        self.mid_entry.insert(0, self.drm.machine_id)
        self.mid_entry.configure(state="readonly")
        self.mid_entry.pack(pady=(0, 10), fill="x", padx=10)
        
        ctk.CTkButton(mid_frame, text="📋 Copiar Machine ID", height=28, width=160,
                      fg_color="#1f6aa5", hover_color="#144870",
                      command=lambda: (self.clipboard_clear(), self.clipboard_append(self.drm.machine_id))
                      ).pack(pady=(0, 10))
        
        key_frame = ctk.CTkFrame(self, fg_color="#2B2B2B", corner_radius=8)
        key_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(key_frame, text="Pegue la Llave de Activación RSA-2048 (Base64):", 
                     font=("Roboto", 11), text_color="#A0A0A0").pack(pady=(8, 2), padx=10, anchor="w")
        
        self.key_textbox = ctk.CTkTextbox(key_frame, height=80, font=("Consolas", 10), fg_color="#1E1E1E")
        self.key_textbox.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(self, text="🔓 Activar VMS Localmente", fg_color="#2ECC71", 
                      hover_color="#27AE60", height=40, font=("Roboto", 14, "bold"),
                      command=self.activate).pack(pady=10)
        
        self.status_label = ctk.CTkLabel(self, text="", font=("Roboto", 13), text_color="#A0A0A0")
        self.status_label.pack(pady=5)
        
    def activate(self):
        val = self.key_textbox.get("1.0", "end").strip()
        if not val:
            self.status_label.configure(text="⚠️ Pegue la llave Base64 en el campo de texto.", text_color="#E74C3C")
            return
            
        if self.drm.activate_license(val):
            self.activated = True
            exp = self.drm.get_expiration_date() or "N/A"
            cams = self.drm.get_max_cameras()
            tier = self.drm.get_tier().upper()
            self.status_label.configure(
                text=f"✅ Activado | Tier: {tier} | Cámaras: {cams} | Expira: {exp}",
                text_color="#2ECC71"
            )
            self.after(1500, self.destroy)
        else:
            self.status_label.configure(
                text="❌ Llave RSA inválida, expirada, o no coincide con este hardware.",
                text_color="#E74C3C"
            )

    def on_close(self):
        import sys
        sys.exit(0)

class Bootloader(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Selección de Sucursal (B2B Tenant)")
        self.geometry("450x350")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.attributes("-topmost", True)
        self.grab_set() 
        self.focus_force()
        
        self.selected_tenant = None
        
        ctk.CTkLabel(self, text="B2B - Gestor Inquilinos", font=("Roboto", 20, "bold"), text_color="#1f6aa5").pack(pady=(20, 10))
        
        self.tenants_dir = ConfigManager.get_appdata_path("Tenants")
        
        self.combo = ctk.CTkComboBox(self, values=self.get_tenant_list())
        self.combo.pack(pady=10, fill="x", padx=50)
        
        ctk.CTkButton(self, text="Ingresar al VMS", command=self.login).pack(pady=5)
        
        ctk.CTkLabel(self, text="--- O CREAR NUEVA ---", font=("Roboto", 12), text_color="#A0A0A0").pack(pady=(15, 5))
        
        self.new_tenant_entry = ctk.CTkEntry(self, placeholder_text="Nuevo_ID_Sucursal")
        self.new_tenant_entry.pack(pady=5, fill="x", padx=50)
        
        ctk.CTkButton(self, text="Crear Nueva Sucursal", fg_color="#2ECC71", hover_color="#27AE60", command=self.create_tenant).pack(pady=5)
        
    def get_tenant_list(self):
        try:
            dirs = [d for d in os.listdir(self.tenants_dir) if os.path.isdir(os.path.join(self.tenants_dir, d))]
            return dirs if dirs else ["Sin sucursales"]
        except Exception:
            return ["Sin sucursales"]

    def login(self):
        val = self.combo.get()
        if val and val != "Sin sucursales":
            self.selected_tenant = val
            ConfigManager.set_active_tenant(self.selected_tenant)
            self.destroy()

    def create_tenant(self):
        val = self.new_tenant_entry.get().strip()
        import re
        if re.match(r"^[a-zA-Z0-9_\-\s]+$", val):
            os.makedirs(os.path.join(self.tenants_dir, val), exist_ok=True)
            self.combo.configure(values=self.get_tenant_list())
            self.combo.set(val)
        else:
            print("ERROR: Caracteres especiales prevenidos.")

    def on_close(self):
        import sys
        sys.exit(0)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    # --- Riesgo 1 (2_PLANNING): evitar crash OpenMP (KMP_DUPLICATE_LIB_OK) ---
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    # --- TASK-5.1: excepthook global + crash log cifrado (AES-256) ---
    from src.security.crash_logger import install_global_excepthook
    install_global_excepthook()

    root = ctk.CTk()
    root.withdraw()
    
    drm = DRMValidator()
    if not drm.validate_license():
        lic_win = LicenseWindow(root, drm)
        root.wait_window(lic_win)
        # CR-06: no confiar en que `wait_window` implique activación. Si la ventana
        # se cerró/destruyó sin activar (excepción interna, cierre programático),
        # abortar. Se re-valida contra disco (fuente de verdad), no solo el flag.
        if not getattr(lic_win, "activated", False) and not drm.validate_license():
            import sys
            print("[VMS] Activación no completada. Cerrando.")
            sys.exit(0)

    bootloader = Bootloader(root)
    root.wait_window(bootloader)
    
    try:
        current = ConfigManager.get_active_tenant()

        # --- TASK-4.3: descifrar la BD del Tenant al montarlo (At-Rest Vault) ---
        from src.security.db_crypto import EncryptedDBVault
        from config.config import get_db_path
        db_vault = EncryptedDBVault(get_db_path())
        try:
            db_vault.unlock()
        except Exception as exc:
            print(f"[VMS][DBVault] No se pudo descifrar la BD ({type(exc).__name__}). "
                  f"Se iniciara una BD nueva.")

        root.destroy()
        app = AppMain(licencia=drm)
        app.mainloop()

        # --- TASK-4.3: re-cifrar la BD en reposo al cerrar el VMS ---
        try:
            db_vault.lock()
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f"[VMS][DBVault] Error al cifrar la BD en reposo: {type(exc).__name__}")
    except ValueError:
        print("Saliendo de forma segura. Bye.")
