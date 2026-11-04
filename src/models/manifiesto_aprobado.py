"""Modelos aprobados (archivo -> sha256), generado desde models/manifest.json.

No editar a mano: python scripts/generar_manifiesto_embebido.py (SPEC/9 §1.8).
"""

MODELOS_APROBADOS: dict[str, str] = {
    "models/rostros/face_detection_yunet_2023mar.onnx": (
        # pragma: allowlist nextline secret
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
    ),
    "models/rostros/face_recognition_sface_2021dec.onnx": (
        # pragma: allowlist nextline secret
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"
    ),
    # pragma: allowlist nextline secret
    "models/yolov8/yolov8n.pt": "31e20dde3def09e2cf938c7be6fe23d9150bbbe503982af13345706515f2ef95",
    # pragma: allowlist nextline secret
    "yolov8n.pt": "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36",
}
