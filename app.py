import os
import subprocess
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# إعداد مسارات الملفات داخل السيرفر الدائم
COOKIES_FILE = 'cookies.txt'
CREDENTIALS_FILE = 'credentials.json'  # ملف الـ JSON الخاص بحساب الخدمة الذي قمت بتحميله
SCOPES = ['https://www.googleapis.com/auth/drive']

def upload_to_drive(file_path, file_name):
    """دالة لرفع الملف إلى جوجل درايف باستخدام حساب الخدمة وجعله عاماً تلقائياً"""
    try:
        credentials = service_account.Credentials.from_service_file(
            CREDENTIALS_FILE, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=credentials)

        file_metadata = {'name': file_name}
        media = MediaFileUpload(file_path, resumable=True)
        
        # رفع الملف
        file = service.files().create(
            body=file_metadata, media_body=media, fields='id, name'
        ).execute()
        
        file_id = file.get('id')

        # جعل الملف عاماً للجميع (Anyone with the link can view)
        permission = {
            'type': 'anyone',
            'role': 'reader',
        }
        service.permissions().create(
            fileId=file_id, body=permission
        ).execute()

        # جلب رابط المشاركة العام
        file_info = service.files().get(
            fileId=file_id, fields='webViewLink'
        ).execute()
        
        return file_info.get('webViewLink')
    except Exception as e:
        print(f"Error uploading to Drive: {e}")
        return None

@app.route('/', methods=['GET'])
def home():
    """صفحة رئيسية بسيطة لتأكيد أن السيرفر يعمل وفي حالة إيقاظ (Live)"""
    return "YouTube Uploader Server is Running 24/7 successfully!", 200

@app.route('/download-yt', methods=['POST'])
def download_youtube():
    """نقطة النهاية (API) التي يستقبل من خلالها موقعك رابط اليوتيوب"""
    data = request.json
    yt_url = data.get('url')

    
    if not yt_url:
        return jsonify({'success': False, 'error': 'No URL provided'}), 400

    output_template = 'downloaded_video.%(ext)s'
    
    # أمر التحميل باستخدام yt-dlp وملف الكوكيز لضمان عدم حدوث حظر أو مشاكل تسجيل دخول
    cmd = [
        'yt-dlp',
        '--cookies', COOKIES_FILE,
        '-f', 'best',
        '-o', output_template,
        yt_url
    ]

    try:
        # تنفيذ عملية التحميل عبر السيرفر
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # البحث عن الملف المحمل وتحديد اسمه ومساره
        downloaded_file = None
        for file in os.listdir('.'):
            if file.startswith('downloaded_video.'):
                downloaded_file = file
                break
                
        if not downloaded_file or not os.path.exists(downloaded_file):
            return jsonify({'success': False, 'error': 'Download failed or file not found'}), 500

        # رفع الملف إلى Google Drive وتوليد الرابط العام
        drive_link = upload_to_drive(downloaded_file, downloaded_file)
        
        # تنظيف مساحة السيرفر وحذف الملف بعد رفعه لعدم امتلاء المساحة
        if os.path.exists(downloaded_file):
            os.remove(downloaded_file)

        if drive_link:
            return jsonify({'success': True, 'link': drive_link})
        else:
            return jsonify({'success': False, 'error': 'Failed to upload to Google Drive'}), 500

    except subprocess.CalledProcessError as e:
        return jsonify({'success': False, 'error': f'yt-dlp error: {e.stderr}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
