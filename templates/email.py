master_email_template: str = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BG-Master</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f7;
            color: #333;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 40px auto;
            background-color: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #0078D7;
        }
        p {
            line-height: 1.6;
        }
        .button {
            display: inline-block;
            margin-top: 20px;
            padding: 12px 25px;
            font-size: 16px;
            color: #fff;
            background-color: #0078D7;
            text-decoration: none;
            border-radius: 5px;
        }
        .button:hover {
            background-color: #005fa3;
        }
        .footer {
            margin-top: 30px;
            font-size: 12px;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Ol&aacute;!</h1>
        <p>Segue o acesso para a plataforma BG-Master.</p>
        <p><strong>Login:</strong> LOGIN_AQUI</p>
        <p><strong>Senha:</strong> SENHA_AQUI</p>
        <p>O link para a plataforma est&aacute; abaixo:</p>
        <a href="https://master.bagaggio.com.br/signin" class="button">CLIQUE AQUI PARA IR PARA A PLATAFORMA</a>
    </div>
</body>
</html>
"""

master_forget_password_email_template: str = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BG-Master</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f7;
            color: #333;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 40px auto;
            background-color: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #0078D7;
        }
        p {
            line-height: 1.6;
        }
        .button {
            display: inline-block;
            margin-top: 20px;
            padding: 12px 25px;
            font-size: 16px;
            color: #fff;
            background-color: #0078D7;
            text-decoration: none;
            border-radius: 5px;
        }
        .button:hover {
            background-color: #005fa3;
        }
        .footer {
            margin-top: 30px;
            font-size: 12px;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Ol&aacute;!</h1>
        <p>Voc&ecirc; est&aacute; recebendo esse e-mail pois solicitou a redefini&ccedil;&atilde;o da sua senha.</p>
        <p>Abaixo voc&ecirc; vai encontrar um c&oacute;digo com validade de 10 minutos:</p>
        <p><strong>C&oacute;digo:</strong> CODIGO_AQUI</p>
    </div>
</body>
</html>
"""

mapa_entidades = {
    'á': '&aacute;', 'é': '&eacute;', 'í': '&iacute;',
    'ó': '&oacute;', 'ú': '&uacute;', 'ç': '&ccedil;',
    'â': '&acirc;', 'ê': '&ecirc;', 'ô': '&ocirc;',
    'ã': '&atilde;', 'õ': '&otilde;', 'à': '&agrave;',
    'Á': '&Aacute;', 'É': '&Eacute;', 'Í': '&Iacute;',
    'Ó': '&Oacute;', 'Ú': '&Uacute;', 'Ç': '&Ccedil;',
    'Â': '&Acirc;', 'Ê': '&Ecirc;', 'Ô': '&Ocirc;',
    'Ã': '&Atilde;', 'Õ': '&Otilde;', 'À': '&Agrave;',
}