FIELDS = {
    'full_name':     'general (GDPR Art.4(1); UU PDP general)',
    'date_of_birth': 'general (GDPR Art.4(1))',
    'phone':         'general (GDPR Art.4(1))',
    'address':       'general (GDPR Art.4(1); location data)',
}

# kind: (ekstensi yang diizinkan, batas ukuran byte)
KINDS = {
    'id_card':  ({'.jpg', '.jpeg', '.png'}, 5 << 20),
    'document': ({'.pdf', '.doc', '.docx', '.xls', '.xlsx'}, 20 << 20),
    'video':    ({'.mp4', '.mov', '.webm', '.mkv'}, 50 << 20),
}

DEFAULT_FOLDERS = ['Dokumen', 'Gambar', 'Video']

KINDS = {
    'id_card':  ({'.jpg', '.jpeg', '.png'}, 5 << 20),
    'image':    ({'.jpg', '.jpeg', '.png', '.gif', '.webp'}, 10 << 20),
    'document': ({'.pdf', '.doc', '.docx', '.xls', '.xlsx'}, 20 << 20),
    'video':    ({'.mp4', '.mov', '.webm', '.mkv'}, 50 << 20),
}