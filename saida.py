import time
import YanAPI

def piscar_led_peito(cor, vezes=1):
    """Faz o LED do botão do peito piscar na cor e quantidade especificadas."""
    for _ in range(vezes):
        YanAPI.sync_set_led(type="button", color=cor, mode="on")
        time.sleep(0.5)
        YanAPI.sync_set_led(type="button", color=cor, mode="off")
        time.sleep(0.5)

def exibir_mensagem(mensagem):
    """Exibe mensagens no terminal."""
    print(mensagem)