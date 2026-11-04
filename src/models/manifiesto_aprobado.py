"""Modelos aprobados (archivo -> sha256), generado desde models/manifest.json.

No editar a mano: python scripts/generar_manifiesto_embebido.py (SPEC/9 §1.8).
"""

MODELOS_APROBADOS: dict[str, str] = {
    "models/rfdetr/rfdetr-nano-coco-int8.onnx": (
        # pragma: allowlist nextline secret
        "0eefa7a4dac204ee93a1ea7e4583e98e8d529a4df31ae0b6631f3a82cc633d3e"
    ),
    "models/rostros/face_detection_yunet_2023mar.onnx": (
        # pragma: allowlist nextline secret
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
    ),
    "models/rostros/face_recognition_sface_2021dec.onnx": (
        # pragma: allowlist nextline secret
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"
    ),
}
