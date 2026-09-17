# Rodar o pipeline no Windows

## Instalar (uma vez)

```powershell
cd C:\Users\<voce>\Downloads\enemwise\pipeline
powershell -ExecutionPolicy Bypass -File .\instalar.ps1
```

O script escolhe uma versão **estável** do Python entre 3.10 e 3.14 (prefere 3.13), cria o ambiente em `.venv`, instala só pacotes prontos e roda os testes. Se algo falhar, ele para e mostra o erro.

**Por que não usar qualquer Python:** numpy, pandas, scipy e pyarrow só publicam pacotes prontos para versões estáveis. Numa versão alfa (por exemplo 3.15.0a3), o pip tenta compilar do código-fonte e pede o Visual Studio.

Sem versão adequada instalada:

```powershell
py -0p                                        # lista as versões presentes
winget install --id Python.Python.3.13 -e     # ou python.org, marcando "Add python.exe to PATH"
```

Depois feche e reabra o PowerShell e rode o `instalar.ps1` de novo.

## Usar (a cada nova janela)

```powershell
cd C:\Users\<voce>\Downloads\enemwise\pipeline
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
enemwise --help
```

Se preferir não ativar o ambiente, troque `enemwise` por `.\.venv\Scripts\python.exe -m enemwise_pipeline.cli`.

## Cuidados específicos do Windows

- **Não use `>` para gravar JSON.** O Windows PowerShell 5.1 grava UTF-16. Use a opção `--saida` dos comandos. O pipeline também lê arquivos com BOM ou UTF-16, caso já exista algum.
- **Caminhos no JSON:** use barras normais, `D:/v92/long/ano={ano}/area={area}/*.parquet`. Barras invertidas precisam ser duplicadas dentro de JSON.
- **Não rode em `C:\Windows\System32`** nem como administrador.
- **Localizar arquivos:** `Get-ChildItem -Recurse -Filter *.parquet D:\pasta | Select-Object -First 5 FullName`
