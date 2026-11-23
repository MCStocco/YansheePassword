# Yanshee QR Passcode Authenticator

Um sistema de segurança interativo desenvolvido para o robô humanoide *UBTECH Yanshee* (modelo de 1GB de RAM). Esta aplicação utiliza a câmera do robô para escanear QR Codes (contendo dígitos/senhas), processar a autenticação e fornecer feedback físico e visual utilizando a SDK YanAPI.

## 🚀 Funcionalidades

*   *Leitura de QR Code:* Utiliza visão computacional para capturar e decodificar QR Codes numéricos de 4 dígitos.
*   *Feedback Visual (LEDs):* Altera a cor do LED do peito do Yanshee para indicar o status da operação (ex: piscando durante a leitura, verde para senha correta, vermelho para incorreta).
*   *Feedback Físico (Servomotores):* Executa rotinas de movimento com os braços (comemoração/sinalização) após a validação bem-sucedida da senha.
*   *Otimização de Memória:* Estruturado com controle de loops e delays para rodar de forma fluida na placa Raspberry Pi do Yanshee com apenas 1GB de RAM, evitando o travamento (OOM - Out of Memory) durante o processamento de imagem.

## 📋 Pré-requisitos

### Hardware
*   Robô UBTECH Yanshee (1GB RAM)
*   Conexão SSH ou acesso ao terminal do robô
*   QR Codes impressos ou na tela do celular (contendo números/senhas)

### Software
*   Python 3.x
*   [YanAPI SDK](https://github.com/UBTECH-Robotics/YanAPI) (Biblioteca oficial de controle do Yanshee)
*   Bibliotecas de processamento de imagem (ex: opencv-python e pyzbar):
    bash
    pip install opencv-python pyzbar
    
(Nota: Certifique-se de que o pacote zbar nativo está instalado no sistema operacional do robô via sudo apt-get install libzbar0)

## 🔧 Instalação

1. Clone este repositório para dentro do diretório do seu Yanshee (via SSH):
   ```bash
   git clone [https://github.com/seu-usuario/yanshee-qr-passcode.git](https://github.com/seu-usuario/yanshee-qr-passcode.git)
   cd yanshee-qr-passcode