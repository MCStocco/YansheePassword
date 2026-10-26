import time
import YanAPI

# Configurações Globais
ROBOT_IP = "127.0.0.1"
TAMANHO_SENHA = 4

def piscar_led_peito(cor, vezes=1):
    """Faz o LED do botão do peito piscar na cor e quantidade especificadas."""
    for _ in range(vezes):
        YanAPI.sync_set_led(type="button", color=cor, mode="on")
        time.sleep(0.5)
        YanAPI.sync_set_led(type="button", color=cor, mode="off")
        time.sleep(0.5)

def ler_qr_code():
    """Aciona a câmara para ler o QR Code e retorna o texto extraído ou None."""
    resultado = YanAPI.sync_do_QR_code_recognition()
    
    if resultado and resultado.get("code") == 0:
        dados = resultado.get("data", {})
        qr_texto = dados.get("contents") or dados.get("content") or "none"
        
        if isinstance(qr_texto, list) and len(qr_texto) > 0:
            qr_texto = qr_texto[0]
            
        texto_limpo = str(qr_texto).strip()
        if texto_limpo and texto_limpo.lower() != "none":
            return texto_limpo
            
    return None

def ler_sequencia(quantidade=TAMANHO_SENHA):
    """Realiza múltiplas leituras de QR codes em sequência e junta os resultados."""
    sequencia = ""
    for i in range(1, quantidade + 1):
        print("\nAponte o {}º QR Code para a câmara...".format(i))
        lido = None
        while lido is None:
            lido = ler_qr_code()
            if lido is None:
                time.sleep(0.5)
                
        print("-> {}º código lido: {}".format(i, lido))
        sequencia += lido
        piscar_led_peito("blue", 1)
        
        if i < quantidade:
            print("Retire o QR code. Prepare o próximo (3 segundos)...")
            time.sleep(3)
            
    return sequencia

def main():
    YanAPI.yan_api_init(ROBOT_IP)
    
    senha_salva = None
    print("=== Sistema de Segurança Yanshee ===")

    while senha_salva is None:
        comando = input(f"\nDigite 'G' para gravar a senha inicial ({TAMANHO_SENHA} leituras): ").strip().lower()
        
        if comando == 'g':
            print("\n--- A GRAVAR SENHA INICIAL ---")
            senha_salva = ler_sequencia(TAMANHO_SENHA)
            print("\nSenha inicial gravada no sistema: {}".format(senha_salva))
            piscar_led_peito("blue", 2)
        else:
            print("Comando inválido. Use 'G' para gravar.")

    print("\n=== Modo de Operação Ativado ===")
    while True:
        comando = input("\nOpções:\n[A] Testar senha\n[G] Gravar nova senha\n[S] Sair\nEscolha: ").strip().lower()
        
        if comando == 'a':
            print("\n--- A VERIFICAR SENHA ---")
            tentativa = ler_sequencia(TAMANHO_SENHA)
            
            print("\nSenha introduzida: {}".format(tentativa))
            if tentativa == senha_salva:
                print("ACESSO CONCEDIDO: A senha está correta!")
                piscar_led_peito("green", 3)
            else:
                print("ACESSO NEGADO: Senha incorreta!")
                piscar_led_peito("red", 3)
                
        elif comando == 'g':
            print("\n--- A REDEFINIR SENHA ---")
            nova_senha = ler_sequencia(TAMANHO_SENHA)
            senha_salva = nova_senha
            print("\nNova senha ({}) gravada com sucesso e a substituir a anterior!".format(senha_salva))
            piscar_led_peito("blue", 2)
                
        elif comando == 's':
            print("A encerrar o sistema de segurança...")
            break
            
        else:
            print("Comando inválido. Escolha 'A', 'G' ou 'S'.")


if _name_ == "_main_":
    main()