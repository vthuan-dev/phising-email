import imaplib
import os
import email
from email.header import decode_header

# Kết nối IMAP
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(os.getenv('IMAP_USER'), os.getenv('IMAP_PASS'))

# Liệt kê thư mục
status, folders = mail.list()
print("Available folders:")
for folder in folders:
    print(f"  {folder.decode()}")

# Kiểm tra SPAM folder
spam_folders = ['[Gmail]/Spam', 'Spam', 'Junk']
for folder_name in spam_folders:
    try:
        status, messages = mail.select(folder_name)
        if status == 'OK':
            num_messages = int(messages[0])
            print(f"\n{folder_name}: {num_messages} emails")
            
            # Lấy 5 email mới nhất
            if num_messages > 0:
                start = max(1, num_messages - 4)
                end = num_messages
                status, msg_ids = mail.search(None, f'{start}:{end}')
                
                if status == 'OK':
                    msg_ids = msg_ids[0].split()
                    print(f"Recent emails in {folder_name}:")
                    for msg_id in msg_ids[-3:]:  # 3 email mới nhất
                        status, msg_data = mail.fetch(msg_id, '(RFC822)')
                        if status == 'OK':
                            email_body = msg_data[0][1]
                            email_message = email.message_from_bytes(email_body)
                            
                            # Decode subject
                            subject = email_message['Subject']
                            if subject:
                                decoded_subject = decode_header(subject)[0][0]
                                if isinstance(decoded_subject, bytes):
                                    decoded_subject = decoded_subject.decode()
                                print(f"  Subject: {decoded_subject}")
                            
                            # Decode sender
                            sender = email_message['From']
                            if sender:
                                decoded_sender = decode_header(sender)[0][0]
                                if isinstance(decoded_sender, bytes):
                                    decoded_sender = decoded_sender.decode()
                                print(f"  From: {decoded_sender}")
                            print()
        else:
            print(f"{folder_name}: Not accessible")
    except Exception as e:
        print(f"{folder_name}: Error - {e}")

mail.close()
mail.logout()
