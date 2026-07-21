# Installation Orin Nano Super — guide pas à pas pour Laurent

Objectif: allumer l'Orin, le connecter à internet, et me donner (Tony) un accès à
distance en SSH via ton VPN WireGuard (celui qui tourne déjà sur ton droplet à
Singapour). Aucune compétence de développeur requise: chaque étape = une action +
comment vérifier qu'elle a marché.

Temps réel à prévoir: environ 2 à 3 heures. Si tout se passe bien, 1 h 15. La
plus grosse partie, c'est le téléchargement et la copie de l'image sur la carte
microSD (fichier de ~9 Go).

Choix technique important (pour aller au plus simple et fiable):
- Le système Ubuntu tourne depuis la carte microSD.
- Le gros SSD NVMe sert uniquement de disque de données, monté sur /data
  (modèles, transcriptions).
- C'est un peu moins rapide que de tout mettre sur le NVMe, mais pour cette phase
  (D3) c'est parfait et ça évite une manipulation compliquée.

Matériel nécessaire:
- L'Orin Nano Super et son alimentation.
- La carte microSD (64 Go minimum, 128 Go conseillé).
- Le SSD NVMe.
- Un écran + un câble DisplayPort. ATTENTION: l'Orin n'a PAS de prise HDMI, il a
  une prise DisplayPort. Si ton écran n'a que du HDMI, il te faut un câble
  "DisplayPort vers HDMI" (quelques euros).
- Un clavier et une souris USB.
- Ton ordinateur (Windows ou Mac) pour préparer la carte microSD.
- Le micro reSpeaker XVF3800 (on le branche plus tard, pas tout de suite).

---

## Étape 1 — Monter le SSD, préparer la carte microSD, et démarrer

### 1a. Installer le SSD NVMe

1. Débranche complètement l'Orin (pas d'alimentation branchée).
2. Retourne la carte de l'Orin: le slot pour le SSD est SOUS la carte. C'est le
   long connecteur "M.2 Key M" (le seul assez long pour un SSD).
3. Retire la petite vis qui est en face du slot (garde-la, tu en as besoin).
4. Glisse le SSD dans le slot, en biais (environ 30°), jusqu'à ce qu'il soit bien
   enfoncé. Puis rabats-le à plat et revisse la petite vis pour le maintenir.

Vérification: le SSD est bien à plat, la vis serrée, il ne bouge pas. On
vérifiera qu'il est reconnu par le logiciel à l'étape 7.

### 1b. Copier le système sur la carte microSD (sur TON ordinateur)

5. Sur ton ordinateur, télécharge l'image JetPack 6.2 pour "Jetson Orin Nano
   Developer Kit" ici:

```
https://developer.nvidia.com/embedded/jetpack-sdk-62
```

Cherche le lien "SD Card Image" pour l'Orin Nano Developer Kit. C'est un gros
fichier .zip (~9 Go). Ne le décompresse pas.

6. Télécharge le logiciel Balena Etcher (gratuit) et installe-le:

```
https://etcher.balena.io
```

7. Mets la carte microSD dans ton ordinateur (avec un lecteur de carte si
   besoin). Ouvre Balena Etcher:
   - "Flash from file" -> choisis le fichier .zip téléchargé.
   - "Select target" -> choisis la carte microSD (bien vérifier que c'est la
     carte et pas un autre disque).
   - Clique "Flash". Ça prend 15 à 30 minutes.

Vérification: Etcher affiche "Flash Complete!" en vert. Retire la carte
proprement (éjecter), puis insère-la dans l'Orin (le slot microSD est sur le
module, à côté du ventilateur).

### 1c. Premier démarrage

8. Branche l'écran (DisplayPort), le clavier et la souris USB, puis
   l'alimentation. L'Orin démarre tout seul.

Vérification: après 1 à 2 minutes, l'écran affiche le logo NVIDIA puis l'écran
d'installation d'Ubuntu.

IMPORTANT — si l'écran reste NOIR après plusieurs minutes: c'est très
probablement que le "firmware" d'usine de l'Orin est trop ancien pour JetPack
6.2. C'est la seule manip que je préfère faire avec toi en direct (appelle-moi /
écris-moi), on ne se lance pas là-dedans à l'aveugle. Beaucoup de kits "Super"
récents démarrent directement, donc il y a de bonnes chances que ça marche du
premier coup.

---

## Étape 2 — Configurer Ubuntu (assistant au premier démarrage)

9. Suis l'assistant à l'écran: langue, fuseau horaire, clavier.
10. Quand il demande de créer un utilisateur, mets EXACTEMENT:
    - Nom / nom d'utilisateur: earbox
    - Mot de passe: celui que tu veux (note-le bien, on en aura besoin).
11. Choisis le réseau: Wi-Fi (entre le mot de passe de ta box) ou câble Ethernet
    (encore plus simple et stable si tu peux).

Vérification: l'Orin arrive sur le bureau Ubuntu. Ouvre le navigateur et va sur
un site web quelconque: si la page s'affiche, internet fonctionne.

Ouvre maintenant l'application "Terminal" (icône avec un carré noir, ou cherche
"Terminal" dans les applications). Toutes les commandes suivantes se tapent dans
ce Terminal, une par une. Astuce: pour coller dans le Terminal, utilise
Ctrl+Maj+V.

---

## Étape 3 — Activer et vérifier le SSH

Le SSH est ce qui me permettra de me connecter à distance. Il est normalement
déjà actif sur JetPack, on le vérifie.

12. Active le SSH (sans risque même s'il est déjà actif):

```
sudo systemctl enable --now ssh
```

13. Vérifie qu'il tourne:

```
systemctl status ssh
```

Vérification: tu dois voir le mot "active (running)" en vert. Appuie sur "q" pour
sortir de l'affichage.

---

## Étape 4 — Raccorder l'Orin à ton VPN WireGuard

On réutilise le VPN WireGuard que tu as déjà monté sur ton droplet à Singapour
(le même où le "rig" est déjà connecté). On ajoute juste l'Orin comme nouveau
membre du VPN.

14. Installe WireGuard sur l'Orin:

```
sudo apt update && sudo apt install -y wireguard
```

Vérification: ça se termine sans erreur. Tu peux contrôler avec:

```
wg --version
```

15. Génère la paire de clés de l'Orin (sa clé privée + sa clé publique):

```
wg genkey | sudo tee /etc/wireguard/orin_private.key | wg pubkey | sudo tee /etc/wireguard/orin_public.key
```

Vérification: affiche la clé publique de l'Orin (tu en auras besoin sur le
droplet):

```
sudo cat /etc/wireguard/orin_public.key
```

Note aussi la clé privée (tu en as besoin à l'étape 17):

```
sudo cat /etc/wireguard/orin_private.key
```

16. Sur ton droplet à Singapour, ajoute l'Orin comme nouveau peer, exactement
    comme tu l'as fait pour le rig: une entrée [Peer] avec la clé publique de
    l'Orin (celle de l'étape 15) et une adresse VPN libre que tu lui attribues
    (par exemple 10.0.0.4/32 — à toi de choisir une IP non utilisée dans ton
    sous-réseau VPN). Recharge la config du serveur comme d'habitude.

    Profites-en pour créer AUSSI un peer pour MOI (Tony): une nouvelle paire de
    clés + une IP VPN libre (par exemple 10.0.0.5). Colle-moi ma config complète
    (fichier .conf) dans le groupe, je m'en sers pour rejoindre le VPN de mon
    côté.

Vérification: côté droplet, ton `wg show` liste maintenant le peer de l'Orin.

17. Sur l'Orin, crée le fichier de config du tunnel:

```
sudo nano /etc/wireguard/wg0.conf
```

Colle ce modèle en remplaçant les 4 valeurs entre <...> (mêmes réglages que pour
le rig): l'adresse VPN que tu as donnée à l'Orin, sa clé privée (étape 15), la
clé publique de ton droplet, et l'adresse publique du droplet:

```
[Interface]
Address = <IP_VPN_DE_L_ORIN>/24
PrivateKey = <CLE_PRIVEE_DE_L_ORIN>

[Peer]
PublicKey = <CLE_PUBLIQUE_DU_DROPLET>
Endpoint = <IP_PUBLIQUE_DU_DROPLET>:51820
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
```

Enregistre: Ctrl+O, Entrée, puis Ctrl+X. (Si ton sous-réseau VPN n'est pas
10.0.0.0/24, mets le tien, le même que pour le rig.)

18. Active le tunnel et fais-le démarrer automatiquement:

```
sudo systemctl enable --now wg-quick@wg0
```

19. Vérifie que le tunnel est monté:

```
sudo wg show
```

Vérification: tu vois le peer du droplet avec une ligne "latest handshake" (une
poignée de main récente = ça communique).

20. Teste en pingant le droplet à travers le tunnel (remplace par l'IP VPN de ton
    droplet, souvent 10.0.0.1):

```
ping -c 3 10.0.0.1
```

Vérification: tu reçois des réponses ("3 received"). Note l'adresse VPN que tu as
donnée à l'Orin (étape 16), tu me l'enverras: c'est celle que j'utiliserai pour
me connecter en SSH.

---

## Étape 5 — Me donner l'accès SSH (Tony)

Une fois que je serai sur le VPN (avec la config que tu m'as collée à l'étape 16),
je pourrai joindre l'Orin par son IP VPN. Il reste à mettre ma clé SSH pour
l'authentification.

### 5B. Ajouter ma clé SSH

Je vais t'envoyer une ligne de texte (ma "clé publique"). Elle ressemble à ça et
COMMENCE par ssh-ed25519 (c'est un exemple, utilise celle que je t'envoie):

```
ssh-ed25519 AAAAC3NzaC1lZDI1... tony@earbox
```

21. Prépare le dossier:

```
mkdir -p ~/.ssh && chmod 700 ~/.ssh
```

22. Ouvre le fichier des clés autorisées avec l'éditeur nano:

```
nano ~/.ssh/authorized_keys
```

Colle la ligne que je t'ai envoyée (Ctrl+Maj+V), sur une seule ligne. Puis
enregistre: Ctrl+O, Entrée, puis Ctrl+X pour quitter.

23. Sécurise le fichier:

```
chmod 600 ~/.ssh/authorized_keys
```

Vérification: affiche le contenu, tu dois voir ma clé:

```
cat ~/.ssh/authorized_keys
```

24. Envoie-moi: l'adresse VPN de l'Orin (étape 16) + confirme que tu as collé ma
    clé. Je teste la connexion et je te dis si c'est bon.

---

## Étape 6 — Brancher le micro reSpeaker XVF3800

25. Branche le micro reSpeaker sur un port USB de l'Orin. Aucun pilote à
    installer, c'est reconnu tout seul.

26. Liste les cartes son / micros détectés:

```
arecord -l
```

Vérification: tu dois voir une ligne mentionnant le reSpeaker (ou "XVF3800" /
"USB Audio"). Fais une capture d'écran (ou recopie le texte) et envoie-la-moi:
j'en ai besoin pour la config audio.

---

## Étape 7 — Formater et monter le SSD NVMe sur /data

ATTENTION: cette étape EFFACE TOUT ce qui se trouve sur le SSD. Le SSD est neuf
donc c'est sans conséquence, mais vérifie bien à l'étape 27 que tu vises le bon
disque (nvme...) et surtout PAS la carte microSD.

27. Identifie le SSD:

```
lsblk
```

Vérification: tu dois voir une ligne "nvme0n1" avec la taille de ton SSD (par
exemple 1T ou 2T). C'est bien lui. La carte microSD apparaît sous le nom
"mmcblk0" — NE PAS y toucher.

28. Crée une table de partitions neuve (efface le disque):

```
sudo parted /dev/nvme0n1 --script mklabel gpt
```

29. Crée une partition qui occupe tout le disque:

```
sudo parted /dev/nvme0n1 --script mkpart primary ext4 0% 100%
```

30. Formate la partition:

```
sudo mkfs.ext4 /dev/nvme0n1p1
```

31. Crée le dossier /data:

```
sudo mkdir -p /data
```

32. Récupère l'identifiant unique (UUID) de la partition:

```
sudo blkid /dev/nvme0n1p1
```

Ça affiche une ligne avec UUID="xxxxxxxx-xxxx-...". Note ce code entre
guillemets.

33. Fais en sorte que /data se remonte automatiquement à chaque démarrage.
    Remplace TON_UUID par le code noté juste avant:

```
echo 'UUID=TON_UUID /data ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab
```

34. Monte le disque maintenant:

```
sudo mount -a
```

35. Donne les droits à l'utilisateur earbox:

```
sudo chown earbox:earbox /data
```

Vérification: la commande suivante doit montrer une ligne avec /data et la taille
de ton SSD:

```
df -h /data
```

---

## C'est fini

Une fois l'étape 5 confirmée (je réussis à me connecter) et l'étape 6 envoyée
(sortie de arecord -l), je prends le relais à distance pour installer le reste.

Récapitulatif de ce que tu dois m'envoyer:
- Ma config WireGuard (le fichier .conf que tu génères pour moi, étape 16).
- L'adresse VPN de l'Orin (étape 16).
- Confirmation que ma clé SSH est collée (étape 23).
- La capture de "arecord -l" (étape 26).

Merci Laurent, et n'hésite pas à m'écrire au moindre blocage, surtout si l'écran
reste noir au premier démarrage.
