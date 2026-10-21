"""Tahap 3–4: centralized preview data shared by Dashboard and My Files."""

DASHBOARD_DATA = {
    'profile': {
        'first_name': 'Salwa',
    },
    'storage': {
        'used': '7.8 GB',
        'total': '10 GB',
        'percentage': 78,
    },
    'totals': {
        'files': 128,
        'folders': 12,
    },
    'recent_files': [],
    'recent_activity': [
        {
            'action': 'Uploaded',
            'file': 'Quarterly report.pdf',
            'time': 'Today, 10:42 AM',
            'kind': 'upload',
        },
        {
            'action': 'Updated',
            'file': 'Product presentation.pptx',
            'time': 'Yesterday, 4:18 PM',
            'kind': 'edit',
        },
        {
            'action': 'Added to',
            'file': 'Photos folder',
            'time': 'Oct 10, 2026',
            'kind': 'folder',
        },
        {
            'action': 'Opened',
            'file': 'Weekend in Kyoto.jpg',
            'time': 'Oct 10, 2026',
            'kind': 'open',
        },
    ],
}

FILE_MANAGER_DATA = {
    'folders': [
        {'name': 'Documents', 'item_count': 18, 'kind': 'folder-documents'},
        {'name': 'Photos', 'item_count': 42, 'kind': 'folder-photos'},
        {'name': 'Videos', 'item_count': 9, 'kind': 'folder-videos'},
        {'name': 'Personal', 'item_count': 12, 'kind': 'folder-personal'},
    ],
    'files': [
        {
            'name': 'Quarterly report.pdf',
            'kind': 'pdf',
            'type': 'PDF document',
            'extension': 'PDF',
            'size': '2.4 MB',
            'size_sort': 2.4,
            'created': 'Oct 09, 2026',
            'modified': 'Today, 10:42 AM',
            'modified_sort': 202610131042,
            'location': 'Documents',
        },
        {
            'name': 'Product presentation.pptx',
            'kind': 'presentation',
            'type': 'Presentation',
            'extension': 'PPTX',
            'size': '8.1 MB',
            'size_sort': 8.1,
            'created': 'Sep 28, 2026',
            'modified': 'Yesterday, 4:18 PM',
            'modified_sort': 202610121618,
            'location': 'Documents',
        },
        {
            'name': 'Weekend in Kyoto.jpg',
            'kind': 'image',
            'type': 'Image',
            'extension': 'JPG',
            'size': '1.2 MB',
            'size_sort': 1.2,
            'created': 'Oct 10, 2026',
            'modified': 'Oct 10, 2026',
            'modified_sort': 202610101100,
            'location': 'Photos',
        },
        {
            'name': 'Family video.mp4',
            'kind': 'video',
            'type': 'Video',
            'extension': 'MP4',
            'size': '126 MB',
            'size_sort': 126,
            'created': 'Oct 02, 2026',
            'modified': 'Oct 08, 2026',
            'modified_sort': 202610081530,
            'location': 'Videos',
        },
    ],
}

# The dashboard and file manager share the same file records.
DASHBOARD_DATA['recent_files'] = FILE_MANAGER_DATA['files'][:4]

# Tahap 7: sampel aktivitas dan hasil perbandingan untuk halaman Recent/Security.
RECENT_DATA = {
    'opened': [
        {'file': FILE_MANAGER_DATA['files'][2], 'time': 'Today, 9:20 AM'},
        {'file': FILE_MANAGER_DATA['files'][0], 'time': 'Yesterday, 2:15 PM'},
        {'file': FILE_MANAGER_DATA['files'][1], 'time': 'Oct 11, 2026'},
    ],
    'uploaded': [
        {'file': FILE_MANAGER_DATA['files'][0], 'time': 'Today, 10:42 AM'},
        {'file': FILE_MANAGER_DATA['files'][3], 'time': 'Oct 08, 2026'},
        {'file': FILE_MANAGER_DATA['files'][2], 'time': 'Oct 06, 2026'},
    ],
    'modified': [
        {'file': FILE_MANAGER_DATA['files'][1], 'time': 'Yesterday, 4:18 PM'},
        {'file': FILE_MANAGER_DATA['files'][0], 'time': 'Oct 10, 2026'},
        {'file': FILE_MANAGER_DATA['files'][3], 'time': 'Oct 08, 2026'},
    ],
}

SECURITY_COMPARISON_DATA = [
    {
        'file': 'Quarterly report.pdf',
        'algorithm': 'AES',
        'encryption_time': '12.4 ms',
        'decryption_time': '10.8 ms',
        'original_size': '2.4 MB',
        'encrypted_size': '2.4 MB',
    },
    {
        'file': 'Quarterly report.pdf',
        'algorithm': 'RC4',
        'encryption_time': '8.7 ms',
        'decryption_time': '7.9 ms',
        'original_size': '2.4 MB',
        'encrypted_size': '2.4 MB',
    },
    {
        'file': 'Quarterly report.pdf',
        'algorithm': 'DES',
        'encryption_time': '15.1 ms',
        'decryption_time': '13.6 ms',
        'original_size': '2.4 MB',
        'encrypted_size': '2.4 MB',
    },
    {
        'file': 'Product presentation.pptx',
        'algorithm': 'AES',
        'encryption_time': '24.6 ms',
        'decryption_time': '21.8 ms',
        'original_size': '8.1 MB',
        'encrypted_size': '8.1 MB',
    },
    {
        'file': 'Product presentation.pptx',
        'algorithm': 'RC4',
        'encryption_time': '18.2 ms',
        'decryption_time': '16.5 ms',
        'original_size': '8.1 MB',
        'encrypted_size': '8.1 MB',
    },
    {
        'file': 'Product presentation.pptx',
        'algorithm': 'DES',
        'encryption_time': '31.3 ms',
        'decryption_time': '28.7 ms',
        'original_size': '8.1 MB',
        'encrypted_size': '8.1 MB',
    },
    {
        'file': 'Weekend in Kyoto.jpg',
        'algorithm': 'AES',
        'encryption_time': '9.2 ms',
        'decryption_time': '8.4 ms',
        'original_size': '1.2 MB',
        'encrypted_size': '1.2 MB',
    },
    {
        'file': 'Weekend in Kyoto.jpg',
        'algorithm': 'RC4',
        'encryption_time': '6.8 ms',
        'decryption_time': '6.1 ms',
        'original_size': '1.2 MB',
        'encrypted_size': '1.2 MB',
    },
    {
        'file': 'Weekend in Kyoto.jpg',
        'algorithm': 'DES',
        'encryption_time': '11.7 ms',
        'decryption_time': '10.2 ms',
        'original_size': '1.2 MB',
        'encrypted_size': '1.2 MB',
    },
]

# Tahap 6: non-sensitive profile preview fields; account name/email can override these.
PROFILE_DATA = {
    'full_name': 'Salwa Putri',
    'first_name': 'Salwa',
    'username': 'salwa.putri',
    'email': 'salwa@example.com',
    'date_of_birth': 'May 14, 1998',
    'phone_number': '+62 812 3456 7890',
    'address': 'Bandung, West Java, Indonesia',
    'initials': 'SP',
}
