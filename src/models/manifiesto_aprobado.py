"""Modelos aprobados (archivo -> sha256), generado desde models/manifest.json.

No editar a mano: python scripts/generar_manifiesto_embebido.py (SPEC/9 §1.8).
"""

MODELOS_APROBADOS: dict[str, str] = {
    # pragma: allowlist nextline secret
    "models/yolov8/yolov8n.pt": "31e20dde3def09e2cf938c7be6fe23d9150bbbe503982af13345706515f2ef95",
    # pragma: allowlist nextline secret
    "yolov8n.pt": "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36",
}
