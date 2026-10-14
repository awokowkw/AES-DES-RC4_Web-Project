FIELDS = {
    'full_name':      'general (GDPR Art.4(1); UU PDP general)',
    'nik':            'identifier (GDPR Art.4(1); UU PDP general)',
    'date_of_birth':  'general (GDPR Art.4(1))',
    'address':        'general (GDPR Art.4(1); location data)',
    'phone':          'general (GDPR Art.4(1))',
    'gender':         'general (UU PDP general)',
    'religion':       'general (UU PDP) / special (GDPR Art.9)',
    'marital_status': 'general (UU PDP general)',
    'health_info':    'specific (UU PDP specific; GDPR Art.9)',
    'bank_account':   'specific (UU PDP financial data)',
}

# kind: (ekstensi yang diizinkan, batas ukuran byte)
KINDS = {
    'id_card':  ({'.jpg', '.jpeg', '.png'}, 5 << 20),
    'document': ({'.pdf', '.doc', '.docx', '.xls', '.xlsx'}, 20 << 20),
    'video':    ({'.mp4', '.mov', '.webm', '.mkv'}, 50 << 20),
}

DEFAULT_FOLDERS = ['Dokumen', 'Gambar', 'Video']