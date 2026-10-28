import customtkinter as ctk
from PIL import Image
import cv2
import math

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, camera_queues: dict):
        super().__init__(master, fg_color="#1E1E1E")
        self.camera_queues = camera_queues
        self.video_labels = {}
        self.is_single_view = False
        self.single_view_cam_id = None
        # Último cuadro recibido de cualquier cámara: el editor de zonas dibuja sobre él.
        self._ultimo_cuadro = None
        
        self.setup_grid()
        self.update_frames()

    def setup_grid(self):
        """Configura la cuadricula matematicamente (NxN) con respecto a la cantidad de camaras"""
        # Desmontar y destruir TODOS los anteriores para evitar mezcla pack/grid
        for widget in self.winfo_children():
            widget.destroy()
        # Limpiar referencias a labels destruidos
        self.video_labels.clear()

        num_cams = len(self.camera_queues)
        if num_cams == 0:
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(0, weight=1)
            lbl = ctk.CTkLabel(self, text="No hay transmisiones B2B activas", font=("Roboto", 16), text_color="#A0A0A0")
            lbl.grid(row=0, column=0, sticky="nsew")
            return
            
        # Logica del multiplexor de N camaras
        cols = math.ceil(math.sqrt(num_cams))
        rows = math.ceil(num_cams / cols)
        
        for r in range(rows):
            self.grid_rowconfigure(r, weight=1)
        for c in range(cols):
            self.grid_columnconfigure(c, weight=1)
            
        for i, cam_id in enumerate(self.camera_queues.keys()):
            if cam_id not in self.video_labels:
                lbl = ctk.CTkLabel(self, text=f"Inicializando Motor IA...\\nCámara: {cam_id}", 
                                   text_color="#FFFFFF", fg_color="#000000", corner_radius=8, font=("Roboto", 14))
                self.video_labels[cam_id] = lbl
                # Vincular Eventos
                lbl.bind("<Double-1>", lambda event, cid=cam_id: self.toggle_single_view(cid))
                # Logica visual Hover UI (opcional en B2B)
                lbl.bind("<Enter>", lambda e, l=lbl: l.configure(fg_color="#1f6aa5"))
                lbl.bind("<Leave>", lambda e, l=lbl: l.configure(fg_color="#000000" if l.cget("image") is None else "transparent"))
            else:
                lbl = self.video_labels[cam_id]
                
            row = i // cols
            col = i % cols
            lbl.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

    def ultimo_cuadro(self):
        """Copia del último cuadro mostrado, o None si todavía no llegó ninguno."""
        return None if self._ultimo_cuadro is None else self._ultimo_cuadro.copy()

    def update_frames(self):
        """Bucle consumidor asincrono Zero-Blocking de TKinter, recupera y muestra el ultimo UI_Frame."""
        try:
            for cam_id, q in self.camera_queues.items():
                if q.empty():
                    continue

                frame_data = None
                # Estrategia Drop-Frame Lado Cliente: Vacia toda la cola atrasada para atrapar el mas reciente.
                # En un VMS no se muestra la historia ahogada, sino el presente mas puro (Cero Latencias).
                while not q.empty():
                    frame_data = q.get_nowait()
                
                if frame_data is not None:
                    _, bgr_frame = frame_data
                    self._ultimo_cuadro = bgr_frame
                    # Transformacion a render PIL nativo
                    rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                    
                    lbl = self.video_labels[cam_id]
                    target_w = lbl.winfo_width()
                    target_h = lbl.winfo_height()
                    
                    # Evitar errores si CustomTkinter transiciona el layout aun (ancho 1px en draw call)
                    if target_w > 10 and target_h > 10:
                        rgb_frame = cv2.resize(rgb_frame, (target_w, target_h))
                    
                    pil_image = Image.fromarray(rgb_frame)
                    # Forzar el rendering size a matchar las cuadriculas flex
                    ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(target_w, target_h))
                    
                    lbl.configure(image=ctk_image, text="") # Borrar texto AI si esta el feed
                    lbl.image = ctk_image
        except Exception as e:
            # Prevencion silenciosa Anti-Crashes. Un frame perdido de UI no debe detener el B2B
            pass

        # Call again on Tkinter idle loop (~30 fps max para VMS multiplexor)
        self.after(33, self.update_frames)

    def toggle_single_view(self, cam_id):
        """Logica asincrona de CustomTkinter para centrar camara (Zoom B2B doble clic)."""
        if not self.is_single_view:
            self.is_single_view = True
            self.single_view_cam_id = cam_id
            
            for cid, lbl in self.video_labels.items():
                if cid != cam_id:
                    lbl.grid_forget() # Oculta rapido sin purgar memoria base
            
            # Formatear la base Grid
            size = self.grid_size()
            for r in range(size[1]):
                self.grid_rowconfigure(r, weight=0)
            for c in range(size[0]):
                self.grid_columnconfigure(c, weight=0)
                
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(0, weight=1)
            
            self.video_labels[cam_id].grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        else:
            self.is_single_view = False
            self.single_view_cam_id = None
            
            for i in range(10): 
                self.grid_rowconfigure(i, weight=0)
                self.grid_columnconfigure(i, weight=0)
                
            # Restaura NxN
            self.setup_grid() 
