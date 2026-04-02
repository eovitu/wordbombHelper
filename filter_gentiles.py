
import os
import unicodedata
import re

def remove_accents(input_str):
    if not input_str: return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    result = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    result = result.replace('ç', 'c').replace('Ç', 'C')
    result = re.sub(r'[^a-zA-Z\-\']', '', result)
    return result

GENTILE_SUFFIXES = set()
base_suffixes = [
    'ense', 'iense', 'anhense', 'alense', 'onense', 'uense', 'oniano', 'niano', 'politano', 'iano',
    'ano', 'ana', 'ino', 'ina', 'ita', 'eta', 'eco', 'enho', 'enha', 'oto', 'ota', 'ol', 'ola', 
    'ao', 'ista', 'ura', 'ero', 'era'
]

for s in base_suffixes:
    GENTILE_SUFFIXES.add(s)
    GENTILE_SUFFIXES.add(s + 's')
    if s.endswith('o'):
        fem = s[:-1] + 'a'
        GENTILE_SUFFIXES.add(fem)
        GENTILE_SUFFIXES.add(fem + 's')

STRICT_GENTILE_SUFFIXES = {
    'ense', 'enses', 'iense', 'ienses', 'anhense', 'anhenses', 'onense', 'onenses', 
    'uense', 'uenses', 'anense', 'anenses', 'oniano', 'onianos', 'oniana', 'onianas'
}

GENTILE_ROOTS = {
    'brasileir', 'portugues', 'paulist', 'mineir', 'catarinens', 'baian', 'fluminens', 'carioca', 'gaucho', 'capixaba', 'potiguar',
    'maranhen', 'paranaen', 'amazonen', 'piauien', 'pernambucan', 'paraiban', 'goian', 'sergipan', 'alagoan', 'acrean', 'rondonien', 
    'roraimen', 'tocantinen', 'matogrossen', 'espanhol', 'frances', 'alemao', 'ingles', 'italian', 'chines', 'japones', 'mexican', 
    'argentin', 'uruguaio', 'paraguaio', 'chilen', 'colombian', 'venezuelan', 'cuban', 'canaden', 'american', 'africano', 'europeu', 
    'asiatico', 'oceanico', 'latin', 'israelense', 'palestino', 'russo', 'grego', 'turco', 'guineense', 'timorense', 'saxao', 'saxonica',
    'angola', 'mocambic', 'guinee', 'cabo-verd', 'timor', 'macau'
}

ISA_LIST = """
Aikanã, Aikewara, Akuntsu, Akuriyó, Amanayé, Amondawa, Anacé, Anambé, Anapuru Muypurá, Aparai, Apiaká, Apinayé, Apurinã, Apyãwa, Aranã, Arapaso, Arapium, Arara, Arara Shawãdawa, Arara Vermelha, Arara da Volta Grande do Xingu, Arara do Rio Amônia, Arara do Rio Branco, Araweté, Arikapú, Aruá, Ashaninka, Asurini do Tocantins, Asurini do Xingu, Atikum, Avá-Canoeiro, Awa Guajá, Aweti, Aymara, Ayoreo, Bakairi, Balatiponé (Umutina), Banawá, Baniwa, Barasana, Bará, Baré, Boe (Bororo), Borari, Canela Apanyekrá, Canela Memortumré, Cara Preta, Chamacoco, Charrua, Chiquitano, Cinta larga, Deni, Desana, Djeoromitxí, Dâw, Enawenê-nawê, Fulkaxó, Fulni-ô, Galibi Kali'na, Galibi-Marworno, Gamela, Gavião Akrãtikatêjê, Gavião Kykatejê, Gavião Parkatêjê, Gavião Pykopjê, Guajajara, Guarani, Guarasugwe, Guató, Gueguê do Sangue, Hi-merimã, Hixkaryana, Huni Kuin (Kaxinawá), Hupd'äh, Ikolen, Ikpeng, Ingarikó, Iny Karajá, Iranxe Manoki, Jamamadi, Jaraqui, Jarawara, Javaé, Jenipapo-Kanindé, Jiahui, Jiripancó, Juma, Ka'apor, Kadiwéu, Kahyana, Kaimbé, Kaingang, Kaixana, Kajkwakratxi (Tapayuna), Kalabaça, Kalankó, Kalapalo, Kamaiurá, Kamba, Kambeba, Kambiwá, Kampé, Kanamari, Kanela do Araguaia, Kanindé, Kanoê, Kantaruré, Kapinawa, Karajá do Norte, Karapanã, Karapotó, Kararayana, Karipuna de Rondônia, Karipuna do Amapá, Kariri, Kariri-Xokó, Karitiana, Karo, Karuazu, Kassupá, Katuenayana, Katukina Pano, Katukina do Rio Biá, Katxuyana, Kawaiwete (Kaiabi), Kaxarari, Kaxixó, Khisêtjê, Kinikinau, Kiriri, Koiupanká, Kokama, Koripako, Korubo, Kotiria, Krahô, Krahô-Kanela, Krenak, Krenyê, Krepynkatejê, Krikatí, Kubeo, Kuikuro, Kujubim, Kulina, Kulina Pano, Kumaruara, Kuntanawa, Kuruaya, Kwazá, Macuxi, Makuna, Makurap, Manchineri, Maraguá, Marubo, Matipu, Matis, Matsés, Mawayana, Maytapu, Mebengôkre (Kayapó), Mehinako, Menky Manoki, Migueleno, Miranha, Mirity-tapuya, Mukurin, Munduruku, Mura, Nadöb, Nahukwá, Nambikwara, Naruvotu, Nawa, Nukini, Ofaié, Okoymoyana, Oro Win, Palikur, Panará, Pankaiuká, Pankararu, Pankararé, Pankaru, Pankará, Parakanã, Paresí, Parintintin, Patamona, Pataxó, Pataxó Hã-Hã-Hãe, Paumari, Payayá, Pipipã, Pira-tapuya, Pirahã, Piripkura, Pitaguary, Potiguara, Puri, Puruborá, Puyanawa, Quechua, Rikbaktsa, Sakurabiat, Sapará, Sateré Mawé, Shanenawa, Siriano, Surui Paiter, Tabajara, Tapajó, Tapeba, Tapuia, Tapuya Kariri, Tariana, Taurepang, Tembé, Tenharim, Terena, Ticuna, Tikmu'un (Maxakali), Tingui Botó, Tiriyó, Torá, Tremembé, Truká, Trumai, Tsohom-dyapa, Tubiba-Tapuia, Tukano, Tumbalalá, Tunayana, Tupaiú, Tupari, Tupinambá, Tupiniquim, Turiwara, Tuxi, Tuxá, Tuyuka, Txikiyana, Uru-Eu-Wau-Wau, Waimiri Atroari, Waiwai, Wajuru, Wajãpi, Wapichana, Warao, Warekena, Wari', Wassu, Wauja, Wayana, Witoto, Xakriabá, Xavante, Xerente, Xerewyana, Xetá, Xikrin Mebengôkre, Xipaya, Xokleng, Xokó, Xowyana, Xukuru, Xukuru-Kariri, Yaminawá, Yanomami, Yawalapiti, Yawanawá, Ye'kwana, Yudja, Yuhupdeh, Yura, Zo'é, Zoró, Zuruahã
"""

INDIGENOUS_PEOPLES = set()
for p in ISA_LIST.split(','):
    p_clean = remove_accents(p.strip()).lower()
    if p_clean:
        # Some are compound: "pataxo haha hae"
        INDIGENOUS_PEOPLES.add(p_clean)
        # Add components
        for part in p_clean.split():
            if len(part) > 3:
                INDIGENOUS_PEOPLES.add(part)

KNOWN_ROOTS_ONLY = {
    'luso', 'afro', 'ibero', 'nipo', 'sino', 'anglo', 'euro', 'germano', 'teuto', 'latino', 'franco', 'indo', 'italo'
}

EXCLUDED_WORDS = {
    'antes', 'reacao', 'reacoes', 'academia', 'academico', 'profissionais', 'profissional', 'reage', 'reagi', 'reagir', 'reaja', 'reajo',
    'abre', 'aberto', 'aberta', 'abertos', 'abertas', 'acaca', 'aca', 'aba', 'aja', 'ala', 'ama', 'ana', 'ara', 'asa', 'ata', 'ava', 'awa',
    'ano-novo', 'alto-falante', 'alto-falantes', 'alto-mar', 'alto-forno', 'afasta', 'afirma', 'ajuda', 'alcance', 'alegria', 'alface', 'alfafa',
    'acre-doce', 'acre-doces', 'amapa-doce', 'amapas-doces'
}

def is_gentile(word):
    w = word.lower()
    if w in EXCLUDED_WORDS: return False
    
    # Indigenous Match (includes roots/components)
    # Check if word contains any indigenous name as a root or is a variant
    # To be safe, we check if any indigenous name is in the word AND it's a wordbomb-style name (often hyphenated)
    
    # Direct match for indigenous names
    if w in INDIGENOUS_PEOPLES: return True
    
    # Root check for gentiles/ethnonyms
    for root in GENTILE_ROOTS:
        if root in w:
            return True
            
    # Hyphenated Logic (very common in towns and groups)
    if '-' in w:
        parts = w.split('-')
        last_part = parts[-1]
        
        for p in parts:
            if p in GENTILE_ROOTS or p in KNOWN_ROOTS_ONLY or p in INDIGENOUS_PEOPLES: return True
            if any(p.endswith(s) for s in STRICT_GENTILE_SUFFIXES): return True
        
        if any(last_part.endswith(s) for s in GENTILE_SUFFIXES):
            if any(x in w for x in ['andorinha', 'abelha', 'abutre', 'aguia', 'arara', 'arnica', 'arua', 'anu', 'arapacu', 'bacurau', 'barranqueiro', 'beija-flor']):
                return False
            if len(last_part) > 3 or last_part in ['ense', 'ano', 'ana', 'ino', 'ina']:
                return True
                
        return False

    # Single Word Logic
    for s in STRICT_GENTILE_SUFFIXES:
        if w.endswith(s) and len(w) > 5:
            return True
            
    return False

portuguese_file = r'c:\Users\vitu\Documents\wordbomb\wordlists\Portuguese.txt'
palindromos_file = r'c:\Users\vitu\Documents\wordbomb\wordlists\Portuguese_palindromos.txt'

if not os.path.exists(portuguese_file):
    print(f"File not found: {portuguese_file}")
    exit(1)

with open(portuguese_file, 'r', encoding='utf-8') as f:
    words = [line.strip() for line in f if line.strip()]

cleaned_main = set()
gentiles_only = set()

for w in words:
    clean = remove_accents(w).lower()
    if not clean: continue
    cleaned_main.add(clean)
    if is_gentile(clean):
        gentiles_only.add(clean)

sorted_main = sorted(list(cleaned_main))
sorted_gentiles = sorted(list(gentiles_only))

with open(portuguese_file, 'w', encoding='utf-8') as f:
    for word in sorted_main:
        f.write(word + '\n')

with open(palindromos_file, 'w', encoding='utf-8') as f:
    for word in sorted_gentiles:
        f.write(word + '\n')

print(f"Final Count. Main: {len(sorted_main)}, Gentiles: {len(sorted_gentiles)}")
