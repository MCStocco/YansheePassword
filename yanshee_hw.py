import time
import cv2
import numpy as np
import YanAPI


class YansheeHardware:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index

    def falar(self, texto):
        """Usa TTS da YanAPI se disponível no ambiente."""
        try:
            if hasattr(YanAPI, "start_voice_tts"):
                YanAPI.start_voice_tts(texto, False)
        except Exception:
            pass

    def set_led(self, cor, modo="breath", duracao=1.5):
        """Controla o LED do peito via YanAPI com segurança."""
        try:
            if hasattr(YanAPI, "set_chest_led"):
                YanAPI.set_chest_led(color=cor, mode=modo)
                if duracao > 0:
                    time.sleep(duracao)
                    YanAPI.set_chest_led(color=cor, mode="off")
        except Exception:
            pass

    def _frame_via_yanapi(self):
        """
        Tenta capturar imagem pelos métodos comuns da YanAPI.
        Se nenhum existir na sua versão, retorna None para usar OpenCV.
        """
        try:
            if hasattr(YanAPI, "get_image"):
                img = YanAPI.get_image()
                if isinstance(img, np.ndarray):
                    return img
            if hasattr(YanAPI, "take_picture"):
                img = YanAPI.take_picture()
                if isinstance(img, np.ndarray):
                    return img
        except Exception:
            pass
        return None

    def capturar_frame(self):
        """Retorna (ok, frame_bgr) usando YanAPI ou OpenCV VideoCapture."""
        frame_api = self._frame_via_yanapi()
        if frame_api is not None:
            return True, frame_api

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            return False, None
        try:
            ok, frame = cap.read()
            return ok, frame if ok else None
        finally:
            cap.release()