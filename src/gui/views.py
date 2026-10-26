"""
Módulos de vistas y selector de cámara para la UI principal del VMS B2B.
Extraído de main_ui.py para respetar el límite de ofuscación de PyArmor trial.
"""
import customtkinter as ctk
import os
from pathlib import Path

from src.gui.buzon_hilo_ui import BuzonHiloUI

# Cada cuánto revisa la vista de reportes los avisos que deja el hilo de la exportación.
INTERVALO_BUZON_MS = 100

def create_employees_view(app_instance, workspace):
    """Panel funcional de registro y eliminación de empleados con FaceRecognizer."""
    from config.config import get_faces_dir, get_db_path
    from src.recognition.face_recognizer import FaceRecognizer
    from src.storage.database_manager import DatabaseManager
    
    frame = ctk.CTkFrame(workspace, fg_color="#1E1E1E")
    
    ctk.CTkLabel(frame, text="Gestión de Empleados", font=("Roboto", 24, "bold"), text_color="#FFFFFF").pack(pady=10, anchor="w")
    
    face_rec = FaceRecognizer(faces_dir=get_faces_dir())
    db = DatabaseManager(db_path=get_db_path())
    
    # --- Registro ---
    reg_frame = ctk.CTkFrame(frame, fg_color="#2B2B2B", corner_radius=10)
    reg_frame.pack(fill="x", pady=10, padx=0)
    ctk.CTkLabel(reg_frame, text="Registrar Nuevo Empleado", font=("Roboto", 16, "bold")).pack(pady=10, padx=15, anchor="w")
    
    name_entry = ctk.CTkEntry(reg_frame, placeholder_text="Nombre del Empleado", height=35)
    name_entry.pack(fill="x", padx=15, pady=5)
    
    dept_entry = ctk.CTkEntry(reg_frame, placeholder_text="Departamento", height=35)
    dept_entry.pack(fill="x", padx=15, pady=5)
    
    pos_entry = ctk.CTkEntry(reg_frame, placeholder_text="Puesto", height=35)
    pos_entry.pack(fill="x", padx=15, pady=5)
    
    status_label = ctk.CTkLabel(reg_frame, text="", font=("Roboto", 12), text_color="#A0A0A0")
    status_label.pack(pady=5, padx=15, anchor="w")
    
    def register_employee():
        import tkinter.filedialog as fd
        name = name_entry.get().strip()
        dept = dept_entry.get().strip()
        pos = pos_entry.get().strip()
        
        if not name:
            status_label.configure(text="⚠️ Ingrese un nombre.", text_color="#E74C3C")
            return
        
        if db.employee_exists(name):
            status_label.configure(text=f"⚠️ '{name}' ya está registrado.", text_color="#E74C3C")
            return
            
        files = fd.askopenfilenames(title="Seleccionar fotos del empleado", filetypes=[("Imágenes", "*.jpg *.jpeg *.png")])
        if not files:
            status_label.configure(text="⚠️ No seleccionó imágenes.", text_color="#E74C3C")
            return
        
        count = face_rec.register_face_burst(list(files), name)
        if count > 0:
            db.save_employee_profile(name, dept, pos)
            status_label.configure(text=f"✅ '{name}' registrado con {count} foto(s).", text_color="#2ECC71")
            name_entry.delete(0, "end")
            dept_entry.delete(0, "end")
            pos_entry.delete(0, "end")
            refresh_employee_list()
        else:
            status_label.configure(text="❌ No se detectó rostro en las fotos.", text_color="#E74C3C")

    ctk.CTkButton(reg_frame, text="📁 Subir Archivo y Registrar", fg_color="#1f6aa5", command=register_employee, height=38).pack(pady=(10, 5), padx=15, fill="x")

    def capture_webcam():
        name = name_entry.get().strip()
        dept = dept_entry.get().strip()
        pos = pos_entry.get().strip()
        if not name:
            status_label.configure(text="⚠️ Ingrese un nombre.", text_color="#E74C3C")
            return
        if db.employee_exists(name):
            status_label.configure(text=f"⚠️ '{name}' ya está registrado.", text_color="#E74C3C")
            return
        
        app_instance._stop_local_camera()
        
        w = ctk.CTkToplevel(app_instance)
        w.title("Captura Biométrica en Vivo")
        w.geometry("640x580")
        w.attributes("-topmost", True)
        w.grab_set()
        
        import cv2
        from PIL import Image
        import tempfile
        
        top_ctrl = ctk.CTkFrame(w, fg_color="#2B2B2B", corner_radius=8)
        top_ctrl.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(top_ctrl, text="Seleccionar Cámara:", font=("Roboto", 12, "bold")).pack(side="left", padx=10, pady=5)
        
        lbl_video = ctk.CTkLabel(w, text="📸 Conectando cámara web...")
        lbl_video.pack(fill="both", expand=True, padx=10, pady=10)
        
        cap_state = {"cap": None}
        
        detected = getattr(app_instance, "_detected_cameras", [])
        if not detected:
            detected = [{"index": i, "label": f"Cámara {i}"} for i in range(4)]
            
        cam_map = {cam["label"]: cam["index"] for cam in detected}
        labels = list(cam_map.keys())
        
        def set_camera(choice):
            idx = cam_map.get(choice, 0)
            if cap_state["cap"]:
                cap_state["cap"].release()
                cap_state["cap"] = None
                
            lbl_video.configure(text=f"📸 Abriendo {choice}...", image="")
            lbl_video.update()
            
            tmp_cap = cv2.VideoCapture(idx)
            if tmp_cap.isOpened():
                cap_state["cap"] = tmp_cap
                lbl_video.configure(text="")
            else:
                lbl_video.configure(text=f"❌ No se pudo abrir {choice}", image="")
        
        cam_combo = ctk.CTkComboBox(top_ctrl, values=labels, width=280, state="readonly", command=set_camera)
        cam_combo.pack(side="left", padx=5, pady=5)
        
        default_label = None
        for lbl in labels:
            idx = cam_map[lbl]
            tmp_cap = cv2.VideoCapture(idx)
            if tmp_cap.isOpened():
                cap_state["cap"] = tmp_cap
                default_label = lbl
                break
                
        if default_label is not None:
            cam_combo.set(default_label)
            lbl_video.configure(text="")
        else:
            lbl_video.configure(text="❌ No se detectó cámara web.")
            w.after(2000, lambda: [w.destroy(), app_instance._start_local_camera()])
            return
            
        captured = []
        
        def update_frame():
            if not w.winfo_exists(): return
            if cap_state["cap"] and cap_state["cap"].isOpened():
                ret, fr = cap_state["cap"].read()
                if ret:
                    df = fr.copy()
                    cv2.putText(df, f"Fotos: {len(captured)}/5 (Presione ESPACIO)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    rgb = cv2.cvtColor(df, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb)
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(600, 480))
                    lbl_video.configure(image=ctk_img, text="")
                    lbl_video.image = ctk_img
            w.after(30, update_frame)
            
        def on_key(e):
            if e.keysym == "space":
                if cap_state["cap"] and cap_state["cap"].isOpened():
                    ret, fr = cap_state["cap"].read()
                    if ret:
                        captured.append(fr.copy())
                        if len(captured) >= 5:
                            finish_capture()
            elif e.keysym == "Escape":
                finish_capture()
                
        def finish_capture():
            if cap_state["cap"]:
                cap_state["cap"].release()
            w.destroy()
            app_instance._start_local_camera()
            
            if captured:
                temp_paths = []
                for i, f in enumerate(captured):
                    tmp = os.path.join(tempfile.gettempdir(), f"tmp_{name}_{i}.jpg")
                    cv2.imwrite(tmp, f)
                    temp_paths.append(tmp)
                count = face_rec.register_face_burst(temp_paths, name)
                if count > 0:
                    db.save_employee_profile(name, dept, pos)
                    status_label.configure(text=f"✅ '{name}': {count} fotos biométricas.", text_color="#2ECC71")
                    name_entry.delete(0, "end")
                    refresh_employee_list()
                else:
                    status_label.configure(text="❌ No se detectó rostro de frente.", text_color="#E74C3C")
        
        w.bind("<Key>", on_key)
        w.protocol("WM_DELETE_WINDOW", finish_capture)
        update_frame()

    ctk.CTkButton(reg_frame, text="📷 Capturar desde Cámara Web", fg_color="#8E44AD", hover_color="#732D91", command=capture_webcam, height=38).pack(pady=(5, 10), padx=15, fill="x")

    # --- Lista de empleados ---
    list_frame = ctk.CTkFrame(frame, fg_color="#2B2B2B", corner_radius=10)
    list_frame.pack(fill="both", expand=True, pady=10, padx=0)
    ctk.CTkLabel(list_frame, text="Empleados Registrados", font=("Roboto", 16, "bold")).pack(pady=10, padx=15, anchor="w")
    
    emp_scroll = ctk.CTkScrollableFrame(list_frame, fg_color="#1E1E1E")
    emp_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))
    
    def refresh_employee_list():
        for w in emp_scroll.winfo_children():
            w.destroy()
        names = db.get_all_employee_names()
        if not names:
            ctk.CTkLabel(emp_scroll, text="No hay empleados registrados.", text_color="#A0A0A0").pack(pady=10)
            return
        for emp_name in names:
            row = ctk.CTkFrame(emp_scroll, fg_color="#2B2B2B", corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"  👤 {emp_name}", font=("Roboto", 14), anchor="w").pack(side="left", padx=10, fill="x", expand=True)
            ctk.CTkButton(row, text="🗑️ Eliminar", width=100, fg_color="#E74C3C", hover_color="#C0392B",
                command=lambda n=emp_name: delete_employee(n)).pack(side="right", padx=10, pady=4)
    
    def delete_employee(name):
        face_rec.delete_face(name)
        db.anonymize_employee(name)
        db.delete_employee_profile(name)
        refresh_employee_list()
    
    refresh_employee_list()
    return frame


def create_zones_view(workspace):
    """Editor de EPP exigido por zona (SPEC/9 §8.3); escribe el formato v2 de zonas."""
    from config.config import get_zonas_file
    from src.gui.panel_zonas import PanelZonas
    from src.gui.presentador_zonas import PresentadorZonas
    from src.ppe.domain.elementos import ElementoEPP

    # D3: la primera versión ofrece casco y chaleco.
    ofrecidos = (ElementoEPP.CASCO, ElementoEPP.CHALECO)
    return PanelZonas(workspace, PresentadorZonas(Path(get_zonas_file()), ofrecidos))


def create_reports_view(workspace):
    """Panel de generación de reportes de asistencia y eficiencia."""
    from config.config import get_db_path, get_export_dir
    from src.storage.database_manager import DatabaseManager
    from src.analysis.report_generator import DatabaseWorker
    
    frame = ctk.CTkFrame(workspace, fg_color="#1E1E1E")
    ctk.CTkLabel(frame, text="Reportes Históricos", font=("Roboto", 24, "bold"), text_color="#FFFFFF").pack(pady=10, anchor="w")
    
    db = DatabaseManager(db_path=get_db_path())
    worker = DatabaseWorker(db)
    
    controls = ctk.CTkFrame(frame, fg_color="#2B2B2B", corner_radius=10)
    controls.pack(fill="x", pady=10)
    
    ctk.CTkLabel(controls, text="Fecha Inicio (YYYY-MM-DD):", font=("Roboto", 13)).pack(side="left", padx=(15, 5), pady=15)
    start_entry = ctk.CTkEntry(controls, placeholder_text="2026-01-01", width=130)
    start_entry.pack(side="left", padx=5, pady=15)
    
    ctk.CTkLabel(controls, text="Fecha Fin:", font=("Roboto", 13)).pack(side="left", padx=(15, 5), pady=15)
    end_entry = ctk.CTkEntry(controls, placeholder_text="2026-12-31", width=130)
    end_entry.pack(side="left", padx=5, pady=15)
    
    report_status = ctk.CTkLabel(frame, text="", font=("Roboto", 13), text_color="#A0A0A0")
    report_status.pack(pady=5, anchor="w")
    
    import re
    _DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

    def generate_report():
        start = start_entry.get().strip() or "2026-01-01"
        end = end_entry.get().strip() or "2026-12-31"

        # CR-02 (OWASP A03): validar formato de fecha ANTES de usarla — defensa en
        # profundidad para el SQL y para el nombre de archivo. Rechazar cualquier
        # cosa que no sea YYYY-MM-DD (bloquea inputs tipo `2026-12-31' OR '1'='1`).
        if not _DATE_RE.match(start) or not _DATE_RE.match(end):
            report_status.configure(
                text="⚠️ Formato de fecha inválido (use YYYY-MM-DD).",
                text_color="#E74C3C")
            return

        export_dir = get_export_dir()
        output = os.path.join(export_dir, f"Reporte_{start}_a_{end}.xlsx")
        # CR-02: placeholders `?` + params, nunca f-string con input de la GUI.
        query = ("SELECT employee_name, date(timestamp) as fecha, zone, inside_zone "
                 "FROM tracking WHERE date(timestamp) BETWEEN ? AND ?")

        report_status.configure(text="⏳ Generando reporte en background...", text_color="#F39C12")

        # Corren en el hilo de la exportación: el aviso se dibuja desde el buzón.
        def on_ok(path, rows):
            frame.buzon.publicar(lambda: report_status.configure(
                text=f"✅ Reporte exportado: {path} ({rows} filas)", text_color="#2ECC71"))
        def on_err(e):
            frame.buzon.publicar(lambda: report_status.configure(
                text=f"❌ Error: {e}", text_color="#E74C3C"))

        worker.generate_excel_async(query, output, on_ok, on_err, params=(start, end))
    
    ctk.CTkButton(controls, text="📊 Exportar Excel", fg_color="#2ECC71", hover_color="#27AE60", command=generate_report, height=35).pack(side="left", padx=15, pady=15)

    frame.buzon = BuzonHiloUI(frame.after, INTERVALO_BUZON_MS)
    frame.buzon.vigilar()
    return frame


def create_tenant_view(workspace):
    """Panel de información del tenant activo."""
    from config.path_utils import ConfigManager
    
    frame = ctk.CTkFrame(workspace, fg_color="#1E1E1E")
    ctk.CTkLabel(frame, text="Multi-Tenant B2B", font=("Roboto", 24, "bold"), text_color="#FFFFFF").pack(pady=10, anchor="w")
    
    try:
        tenant = ConfigManager.get_active_tenant()
    except ValueError:
        tenant = "Sin seleccionar"
    
    info = ctk.CTkFrame(frame, fg_color="#2B2B2B", corner_radius=10)
    info.pack(fill="x", pady=10)
    ctk.CTkLabel(info, text=f"Sucursal Activa:  {tenant}", font=("Roboto", 16), text_color="#2ECC71").pack(pady=15, padx=15, anchor="w")
    ctk.CTkLabel(info, text=f"Datos en: {ConfigManager.get_tenant_path()}", font=("Roboto", 12), text_color="#A0A0A0").pack(pady=(0, 15), padx=15, anchor="w")
    
    ctk.CTkLabel(frame, text="Para cambiar de sucursal, reinicie la aplicación.", font=("Roboto", 13), text_color="#A0A0A0").pack(pady=10, anchor="w")
    return frame


def build_camera_selector(app_instance, sidebar_frame):
    """Construye el selector de cámara en el sidebar (como v1.0.0)."""
    # Separador visual
    sep = ctk.CTkFrame(sidebar_frame, height=1, fg_color="#444444")
    sep.pack(fill="x", padx=15, pady=(20, 10))
    
    # Titulo de sección
    ctk.CTkLabel(
        sidebar_frame, text="📹 Cámara",
        font=("Roboto", 14, "bold"), text_color="#FFFFFF"
    ).pack(padx=20, anchor="w", pady=(5, 5))
    
    # Dropdown de cámaras
    app_instance._cam_combo = ctk.CTkComboBox(
        sidebar_frame,
        values=["Escaneando..."],
        font=("Roboto", 12),
        dropdown_font=("Roboto", 12),
        width=210,
        height=32,
        state="readonly",
        fg_color="#1E1E1E",
        border_color="#1f6aa5",
        button_color="#1f6aa5",
        button_hover_color="#144870"
    )
    app_instance._cam_combo.pack(padx=20, pady=(0, 5))
    
    # Botones de acción (Conectar + Refrescar)
    btn_row = ctk.CTkFrame(sidebar_frame, fg_color="transparent")
    btn_row.pack(padx=20, fill="x", pady=(0, 5))
    
    app_instance._cam_connect_btn = ctk.CTkButton(
        btn_row, text="▶ Conectar",
        font=("Roboto", 12), height=30, width=130,
        fg_color="#2ECC71", hover_color="#27AE60",
        command=app_instance._on_camera_selected
    )
    app_instance._cam_connect_btn.pack(side="left", padx=(0, 5))
    
    app_instance._cam_refresh_btn = ctk.CTkButton(
        btn_row, text="🔄",
        font=("Roboto", 14), height=30, width=40,
        fg_color="#555555", hover_color="#777777",
        command=app_instance._scan_cameras
    )
    app_instance._cam_refresh_btn.pack(side="left")
    
    # Input manual
    manual_row = ctk.CTkFrame(sidebar_frame, fg_color="transparent")
    manual_row.pack(padx=20, fill="x", pady=(0, 5))
    
    app_instance._cam_manual_entry = ctk.CTkEntry(
        manual_row, placeholder_text="Índice manual",
        font=("Roboto", 11), height=28, width=100,
        fg_color="#1E1E1E", border_color="#555555"
    )
    app_instance._cam_manual_entry.pack(side="left", padx=(0, 5))
    
    ctk.CTkButton(
        manual_row, text="Usar",
        font=("Roboto", 11), height=28, width=65,
        fg_color="#8E44AD", hover_color="#732D91",
        command=app_instance._on_manual_camera
    ).pack(side="left")
    
    # Estado
    app_instance._cam_status_label = ctk.CTkLabel(
        sidebar_frame, text="⏳ Escaneando cámaras...",
        font=("Roboto", 11), text_color="#A0A0A0"
    )
    app_instance._cam_status_label.pack(padx=20, anchor="w", pady=(0, 5))
