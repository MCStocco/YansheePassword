import time
from entrada import ler_qr_code
from saida import piscar_led_peito, exibir_mensagem

def ler_sequencia_completa(quantidade):
    """Realiza múltiplas leituras de QR codes em sequência e junta os resultados."""
    sequencia = ""
    for i in range(1, quantidade + 1):
        exibir_mensagem(f"\nAponte o {i}º QR Code para a câmara...")
        lido = None
        
        while lido is None:
            lido = ler_qr_code()
            if lido is None:
                time.sleep(0.5)
                
        exibir_mensagem(f"-> {i}º código lido: {lido}")
        sequencia += lido
        piscar_led_peito("blue", 1)
        
        if i < quantidade:
            exibir_mensagem("Retire o QR code. Prepare o próximo (3 segundos)...")
            time.sleep(3)
            
    return sequencia

def validar_acesso(tentativa, senha_salva):
    """Compara a senha inserida com a senha armazenada."""
    return tentativa == senha_salva