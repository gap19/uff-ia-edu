# Deploy no Firebase Hosting (plano gratuito)

O dashboard é publicado como **site 100% estático** no Firebase Hosting (plano
Spark, sem billing). Todas as respostas da API são pré-computadas por
`scripts/export_static.py` e salvas em `dist/` (~7 MB), junto com o HTML, os
assets e o relatório PDF pré-gerado.

> **Pré-requisito:** os dados processados (`data/processed/`) são versionados
> com Git LFS. Num clone novo, rode `git lfs install && git lfs pull` antes de
> exportar. A geração do PDF requer as bibliotecas de sistema do WeasyPrint
> (Pango/Cairo — ver `Dockerfile`).

## 1. Gerar o build estático

```bash
python scripts/export_static.py          # gera dist/ completo (JSONs + HTML + PDF)
python scripts/export_static.py --skip-pdf   # mais rápido, sem regenerar o PDF
```

## 2. Criar o projeto Firebase (uma vez)

1. Acesse <https://console.firebase.google.com> → **Adicionar projeto**.
2. Crie um projeto **novo** (não reutilize o projeto GCP pago). No plano Spark
   não há billing vinculado — não adicione cartão nem faça upgrade para Blaze.

## 3. Instalar o CLI e fazer deploy

```bash
# CLI standalone (não precisa de Node.js)
curl -sL https://firebase.tools | bash

firebase login --no-localhost   # use --no-localhost em container/codespace
firebase use --add              # selecione o projeto criado, alias "default"
firebase deploy --only hosting
```

O site fica em `https://<projeto>.web.app`.

## 4. Atualizar o site depois de mudanças

```bash
python scripts/export_static.py
firebase deploy --only hosting
```

## Limites do plano gratuito (referência)

- Armazenamento: 10 GB (o build usa ~7 MB)
- Transferência: 360 MB/dia
- Sem funções server-side — por isso o site é estático

## Notas da conversão para estático

- `scripts/export_static.py` injeta `<meta name="static-data" content="true">` no
  `<head>` do `index.html` gerado (sem nenhum `<script>` inline), permitindo uma
  `Content-Security-Policy` estrita (`script-src 'self'`) tanto no servidor
  local quanto no Firebase Hosting (`firebase.json`). `frontend/static/js/app.js`
  detecta essa meta tag (mantendo `window.STATIC_DATA` apenas como fallback para
  testes) e passa a buscar arquivos `/api/<rota>__<param>-<valor>...json` em vez
  de chamar a API dinâmica. O esquema de nomes é espelhado por `slug_path()` no
  exportador — **manter as duas funções em sincronia**.
- Todos os assets de terceiros (Apache ECharts, Bootstrap, Bootstrap Icons,
  KaTeX e fonte Inter) já são auto-hospedados e copiados para
  `dist/static/vendor/` (servidos com `Cache-Control: public, max-age=31536000,
  immutable`, sem dependência de CDNs externos).
- O relatório PDF não é mais gerado sob demanda: o exportador pré-gera o
  relatório completo (todas as seções, incluindo cruzamentos, com apêndice
  para todas as séries e disciplinas; gráficos de série única usam 9º EF / LP)
  em `dist/reports/`. Cada exportação apaga `dist/api/` antes de gravar, para
  não publicar JSONs obsoletos. Os filtros do modal de relatório ficam
  desabilitados no site estático.
- O servidor FastAPI continua funcionando normalmente para desenvolvimento
  local (`uvicorn backend.api.app:app`) — sem a flag, o frontend usa a API
  dinâmica como antes.

## Desligar o GCP pago

Depois de confirmar que o site no Firebase está no ar:

- **Se o projeto GCP antigo só servia este dashboard** (recomendado): exclua o
  projeto inteiro no console (IAM e administração → Configurações → Encerrar)
  ou via `gcloud projects delete <PROJECT_ID>`. Isso elimina Cloud Run,
  Artifact Registry, storage e qualquer outra cobrança residual de uma vez.
- **Se o projeto tem outras coisas**: remova só os recursos do dashboard
  (serviço do Cloud Run, imagens no Artifact Registry, buckets) e confira em
  Faturamento → Relatórios qual SKU gerava a cobrança.
