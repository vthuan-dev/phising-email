import imaplib
import os
import email
import logging
from email.header import decode_header

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('imap_debug')

# Kết nối IMAP
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(os.getenv('IMAP_USER'), os.getenv('IMAP_PASS'))

# Liệt kê thư mục
logger.info('Listing folders...')
status, folders = mail.list()
for folder in folders:
    logger.info(f'Raw folder: {folder.decode()}')
    folder_parts = folder.decode().split(' \"/\" ')
    if len(folder_parts) > 1:
        folder_name = folder_parts[1].strip('"')
        logger.info(f'Parsed folder name: {folder_name}')

# Kiểm tra các thư mục
folders_to_check = set(['INBOX'])
for folder in folders:
    folder_parts = folder.decode().split(' \"/\" ')
    if len(folder_parts) > 1:
        name = folder_parts[1].strip('"')
        if any(key in name.lower() for key in ['spam', 'junk', 'thư rác']):
            folders_to_check.add(name)
            logger.info(f'Found SPAM folder: {name}')

logger.info(f'Folders to check: {folders_to_check}')

# Kiểm tra mỗi thư mục
for folder_name in folders_to_check:
    try:
        logger.info(f'Selecting folder: {folder_name}')
        status, messages = mail.select(folder_name, readonly=True)
        if status != 'OK':
            logger.error(f'Select {folder_name}: {status}')
            continue
        
        num_messages = int(messages[0])
        logger.info(f'Found {num_messages} messages in {folder_name}')
        
        # Lấy 5 email mới nhất
        if num_messages > 0:
            status, messages = mail.search(None, 'ALL')
            if status != 'OK':
                logger.error(f'Search in {folder_name} failed: {status}')
                continue
                
            message_ids = messages[0].split()
            latest_ids = message_ids[-5:] if len(message_ids) > 5 else message_ids
            
            for msg_id in latest_ids:
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status != 'OK':
                    logger.error(f'Fetch message {msg_id} failed: {status}')
                    continue
                    
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                subject = msg.get('Subject', '')
                if subject:
                    subject_bytes, encoding = decode_header(subject)[0]
                    if isinstance(subject_bytes, bytes):
                        subject = subject_bytes.decode(encoding if encoding else 'utf-8', errors='replace')
                
                from_addr = msg.get('From', '')
                
                logger.info(f'Message ID: {msg_id.decode()}, Subject: {subject}, From: {from_addr}')
    except Exception as e:
        logger.error(f'Error with folder {folder_name}: {e}')

mail.logout()
logger.info('Done!')
