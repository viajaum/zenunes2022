import pandas as pd
import json
import urllib.request
import urllib.parse
import time
from datetime import datetime

def geocode_osm(endereco_completo):
    """Geocodifica usando OpenStreetMap"""
    params = {"q": endereco_completo, "format": "json", "limit": 1, "accept-language": "pt-BR"}
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "VoterGeocoding/1.0 (pesquisa@exemplo.com)"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
        if data and len(data) > 0:
            return {
                "latitude": float(data[0]['lat']), 
                "longitude": float(data[0]['lon']),
                "source": "osm"
            }
    except Exception as e:
        print(f"Erro: {e}")
    
    return {"latitude": None, "longitude": None, "source": None}

# Lê CSV e filtra candidato
print("📖 Lendo arquivo CSV...")
df = pd.read_csv('votacao_secao_2022_RS.csv', sep=';', encoding='latin1')
df_candidato = df[(df['CD_CARGO'] == 7) & (df['NR_TURNO'] == 1) & (df['NR_VOTAVEL'] == 13500)]

if len(df_candidato) == 0:
    print("❌ Candidato 13500 não encontrado!")
    exit()

nome_candidato = df_candidato['NM_VOTAVEL'].iloc[0]
print(f"✅ Candidato: {nome_candidato}")

# Locais únicos do candidato
locais = df_candidato[['NM_MUNICIPIO', 'NM_LOCAL_VOTACAO', 'DS_LOCAL_VOTACAO_ENDERECO']].drop_duplicates()
print(f"   Locais de votação: {len(locais)}")

# Carrega coordenadas dos municípios
print("\n📂 Carregando coordenadas dos municípios...")
try:
    with open('municipios_rs_geocodificados.json', 'r', encoding='utf-8') as f:
        municipios_data = json.load(f)
    
    # Dicionário com coordenadas dos municípios (usando as mesmas chaves)
    municipio_coords = {}
    for m in municipios_data['municipios']:
        municipio_coords[m['nome']] = {
            "latitude": m['latitude'],
            "longitude": m['longitude'],
            "source": "municipio_fallback"
        }
    print(f"✅ Coordenadas de {len(municipio_coords)} municípios carregadas")
except FileNotFoundError:
    print("⚠️  Arquivo municipios_rs_geocodificados.json não encontrado!")
    print("   Executando sem fallback...")
    municipio_coords = {}

# Geocodifica
print(f"\n🌍 Geocodificando {len(locais)} locais...")
print("   (1 segundo por local, aguarde...)\n")

resultados = []
sucesso = 0
fallback = 0
falha = 0

for i, (_, row) in enumerate(locais.iterrows(), 1):
    municipio = row['NM_MUNICIPIO']
    local_nome = row['NM_LOCAL_VOTACAO']
    endereco = row['DS_LOCAL_VOTACAO_ENDERECO'] if pd.notna(row['DS_LOCAL_VOTACAO_ENDERECO']) else ""
    
    # Mostra progresso
    percentual = (i / len(locais)) * 100
    print(f"  [{i}/{len(locais)}] ({percentual:.1f}%) - {municipio}: {local_nome[:40]}...", end=" ", flush=True)
    
    # Tenta geocodificar o local específico
    if endereco:
        endereco_completo = f"{endereco}, {municipio}, Rio Grande do Sul, Brasil"
    else:
        endereco_completo = f"{local_nome}, {municipio}, Rio Grande do Sul, Brasil"
    
    coords = geocode_osm(endereco_completo)
    
    # Se falhou, tenta fallback para coordenadas do município
    if not coords['latitude'] and municipio in municipio_coords:
        coords = municipio_coords[municipio]
        coords['source'] = 'municipio_fallback'
        print("📍 (fallback)")
        fallback += 1
    elif coords['latitude']:
        print("✅")
        sucesso += 1
    else:
        print("❌")
        falha += 1
    
    resultados.append({
        "municipio": municipio,
        "codigo_municipio": int(row['CD_MUNICIPIO']) if 'CD_MUNICIPIO' in row else None,
        "nome_local": local_nome,
        "endereco": endereco,
        "latitude": coords['latitude'],
        "longitude": coords['longitude'],
        "fonte": coords.get('source', 'nao_encontrado')
    })
    
    # Aguarda 1 segundo para respeitar política do Nominatim
    time.sleep(1)

# Salva resultado
output = {
    "metadata": {
        "ano": 2022,
        "uf": "RS",
        "candidato": nome_candidato,
        "numero": "13500",
        "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fonte": "TSE - Votação por Seção",
        "geocoding": "OpenStreetMap Nominatim",
        "total_locais": len(resultados),
        "estatisticas": {
            "geocodificados_diretamente": sucesso,
            "fallback_municipio": fallback,
            "nao_encontrados": falha,
            "taxa_sucesso": f"{(sucesso+fallback)/len(resultados)*100:.2f}%"
        }
    },
    "locais_votacao": resultados
}

nome_arquivo = f'candidato_13500_locais_coords.json'
with open(nome_arquivo, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n" + "="*60)
print(f"✅ PROCESSAMENTO CONCLUÍDO!")
print(f"="*60)
print(f"\n📊 ESTATÍSTICAS:")
print(f"   Total de locais: {len(resultados)}")
print(f"   ✅ Geocodificados diretamente: {sucesso}")
print(f"   📍 Fallback (coordenadas do município): {fallback}")
print(f"   ❌ Não encontrados: {falha}")
print(f"   📈 Taxa de sucesso total: {(sucesso+fallback)/len(resultados)*100:.2f}%")
print(f"\n📁 Arquivo gerado: {nome_arquivo}")

# Mostra alguns exemplos
print(f"\n📋 Exemplos de locais geocodificados:")
for i, local in enumerate(resultados[:5]):
    if local['latitude']:
        print(f"   {i+1}. {local['municipio']} - {local['nome_local'][:50]}")
        print(f"      📍 ({local['latitude']}, {local['longitude']}) - Fonte: {local['fonte']}")
    else:
        print(f"   {i+1}. {local['municipio']} - {local['nome_local'][:50]} - ❌ Sem coordenadas")