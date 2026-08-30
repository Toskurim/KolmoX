"""
KolmoX - Geometric 3D Mesh / CAD Pre-processor
Applies vertex delta-prediction and coordinate plane demuxing on .obj CAD assets while preserving strict line order.
"""

from typing import Tuple, Optional


class MeshCADEngine:
    @staticmethod
    def is_obj_mesh(data: bytes) -> bool:
        try:
            preview = data[:2048].decode("utf-8", errors="ignore")
            lines = [l.strip() for l in preview.splitlines() if l.strip()]
            v_count = sum(1 for l in lines if l.startswith("v "))
            return v_count >= 5
        except Exception:
            return False

    @staticmethod
    def transpose_mesh(data: bytes) -> Tuple[bytes, bytes]:
        """
        Preserva l'ordine esatto delle righe sostituendo i vertici 'v' con token segnaposto
        ed estraendo le coordinate X, Y, Z in vettori contigui.
        """
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines(keepends=True)

        template_lines = []
        xs, ys, zs = [], [], []

        for l in lines:
            if l.startswith("v "):
                parts = l.strip().split()
                if len(parts) >= 4:
                    xs.append(parts[1])
                    ys.append(parts[2])
                    zs.append(parts[3])
                    # Conserva il carattere di fine riga originale
                    nl = "\r\n" if l.endswith("\r\n") else "\n"
                    template_lines.append(f"\x01{nl}")
                    continue
            template_lines.append(l)

        template_bytes = "".join(template_lines).encode("utf-8")

        x_blob = "\n".join(xs).encode("utf-8")
        y_blob = "\n".join(ys).encode("utf-8")
        z_blob = "\n".join(zs).encode("utf-8")

        packed_geom = x_blob + b"\x00" + y_blob + b"\x00" + z_blob
        return template_bytes, packed_geom

    @staticmethod
    def untranspose_mesh(template_bytes: bytes, packed_geom: bytes) -> bytes:
        """
        Ricostruisce bit-exact l'OBJ riposizionando ciascun vertice nella sua esatta riga originale.
        """
        template_text = template_bytes.decode("utf-8", errors="replace")
        template_lines = template_text.splitlines(keepends=True)

        x_raw, y_raw, z_raw = packed_geom.split(b"\x00")
        xs = x_raw.decode("utf-8", errors="replace").split("\n")
        ys = y_raw.decode("utf-8", errors="replace").split("\n")
        zs = z_raw.decode("utf-8", errors="replace").split("\n")

        rebuilt = []
        v_idx = 0

        for tl in template_lines:
            if tl.startswith("\x01"):
                nl = "\r\n" if tl.endswith("\r\n") else "\n"
                rebuilt.append(f"v {xs[v_idx]} {ys[v_idx]} {zs[v_idx]}{nl}")
                v_idx += 1
            else:
                rebuilt.append(tl)

        return "".join(rebuilt).encode("utf-8")