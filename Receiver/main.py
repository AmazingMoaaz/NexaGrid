import http.server
import socketserver
import json
import os
import base64
import mimetypes
import logging
from datetime import datetime
from urllib.parse import unquote
import hashlib
import uuid

# Configure advanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('upload_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global upload directory variable
UPLOAD_DIR = None

class AdvancedUploadHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def log_message(self, format, *args):
        """Override default logging to use our logger"""
        logger.info(f"{self.client_address[0]} - {format % args}")
    
    def get_file_info(self, filename, content):
        """Get comprehensive file information"""
        mime_type, encoding = mimetypes.guess_type(filename)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        
        # Determine if file is binary or text
        is_binary = mime_type.startswith(('image/', 'video/', 'audio/', 'application/')) and not mime_type.startswith('application/json')
        
        # Calculate file hash for integrity checking
        if isinstance(content, bytes):
            file_hash = hashlib.md5(content).hexdigest()
        else:
            file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        return {
            'mime_type': mime_type,
            'encoding': encoding,
            'is_binary': is_binary,
            'hash': file_hash
        }
    
    def sanitize_filename(self, filename):
        """Sanitize filename while preserving original name as much as possible"""
        # Remove path separators and dangerous characters
        filename = filename.replace('\\', '_').replace('/', '_')
        filename = ''.join(c for c in filename if c.isalnum() or c in '._-() ')
        
        # Ensure filename is not empty
        if not filename.strip():
            filename = f"unnamed_file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return filename.strip()
    
    def ensure_unique_filename(self, filepath):
        """Ensure filename is unique by adding counter if needed"""
        if not os.path.exists(filepath):
            return filepath
        
        base, ext = os.path.splitext(filepath)
        counter = 1
        while os.path.exists(f"{base}_{counter}{ext}"):
            counter += 1
        
        return f"{base}_{counter}{ext}"
    
    def do_GET(self):
        logger.info(f"📥 GET request from {self.client_address[0]} to: {self.path}")
        
        if self.path.startswith('/files/'):
            filename = unquote(self.path[7:])  # Remove '/files/' prefix and decode URL
            filename = self.sanitize_filename(filename)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            upload_dir = os.path.join(script_dir, 'received Files')
            filepath = os.path.join(upload_dir, filename)
            
            if os.path.exists(filepath):
                try:
                    file_info = self.get_file_info(filename, b'')  # We don't need content for info
                    
                    self.send_response(200)
                    self.send_header('Content-type', file_info['mime_type'])
                    self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                    self.send_header('X-File-Hash', file_info['hash'])
                    self.end_headers()
                    
                    with open(filepath, 'rb') as f:
                        content = f.read()
                        self.wfile.write(content)
                    
                    logger.info(f"✅ File downloaded: {filename} ({len(content)} bytes)")
                    
                except Exception as e:
                    logger.error(f"❌ Error serving file {filename}: {str(e)}")
                    self.send_response(500)
                    self.end_headers()
            else:
                logger.warning(f"⚠️ File not found: {filename}")
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {'error': 'File not found', 'filename': filename}
                self.wfile.write(json.dumps(error_response).encode())
        else:
            super().do_GET()
    
    def parse_multipart_data(self, post_data, boundary):
        """Advanced multipart form data parser"""
        try:
            boundary_bytes = boundary.encode()
            parts = post_data.split(b'--' + boundary_bytes)
            
            files = []
            for part in parts:
                if b'Content-Disposition' in part:
                    lines = part.split(b'\r\n')
                    
                    # Parse headers
                    headers = {}
                    content_start_idx = 0
                    disposition_line = ""
                    
                    for i, line in enumerate(lines):
                        if line == b'':
                            content_start_idx = i + 1
                            break
                        if b':' in line:
                            line_str = line.decode('utf-8', errors='ignore')
                            key, value = line_str.split(':', 1)
                            headers[key.strip().lower()] = value.strip()
                            if key.strip().lower() == 'content-disposition':
                                disposition_line = value.strip()
                    
                    # Extract filename from Content-Disposition header
                    filename = 'unknown_file'
                    
                    # Try multiple patterns for filename extraction
                    if disposition_line:
                        logger.info(f"🔍 Parsing disposition: {disposition_line}")
                        
                        # Pattern 1: filename="value"
                        if 'filename="' in disposition_line:
                            try:
                                filename = disposition_line.split('filename="')[1].split('"')[0]
                                logger.info(f"📝 Extracted filename (quoted): {filename}")
                            except IndexError:
                                pass
                        
                        # Pattern 2: filename=value (no quotes)
                        elif 'filename=' in disposition_line:
                            try:
                                filename_part = disposition_line.split('filename=')[1]
                                filename = filename_part.split(';')[0].strip()
                                # Remove quotes if present
                                if filename.startswith('"') and filename.endswith('"'):
                                    filename = filename[1:-1]
                                logger.info(f"📝 Extracted filename (unquoted): {filename}")
                            except IndexError:
                                pass
                    
                    # Fallback: Search for filename in the raw part data
                    if filename == 'unknown_file':
                        try:
                            part_str = part.decode('utf-8', errors='ignore')
                            
                            # Look for various filename patterns in the entire part
                            patterns = [
                                r'filename="([^"]+)"',
                                r'filename=([^;\s\r\n]+)',
                                r'name="file"[^;]*;\s*filename="([^"]+)"',
                                r'name="file"[^;]*;\s*filename=([^;\s\r\n]+)'
                            ]
                            
                            import re
                            for pattern in patterns:
                                match = re.search(pattern, part_str)
                                if match:
                                    filename = match.group(1).strip()
                                    logger.info(f"📝 Extracted filename via regex ({pattern}): {filename}")
                                    break
                                    
                        except Exception as e:
                            logger.warning(f"⚠️ Filename extraction fallback failed: {e}")
                    
                    # Log what we found
                    logger.info(f"📋 Final filename determined: {filename}")
                    
                    # Check if this part actually contains file data
                    if b'filename=' in part:
                        # Extract content
                        content_lines = lines[content_start_idx:]
                        if content_lines and content_lines[-1] == b'':
                            content_lines = content_lines[:-1]
                        
                        content = b'\r\n'.join(content_lines)
                        
                        # Skip empty content
                        if content:
                            files.append({
                                'filename': filename,
                                'content': content,
                                'headers': headers
                            })
                            logger.info(f"📦 Found file: {filename} ({len(content)} bytes)")
            
            return files
            
        except Exception as e:
            logger.error(f"❌ Multipart parsing error: {str(e)}")
            # Debug: Log the raw data (first 1000 chars for better debugging)
            try:
                raw_preview = post_data[:1000].decode('utf-8', errors='ignore')
                logger.error(f"🔍 Raw data preview (1000 chars): {raw_preview}")
            except:
                logger.error(f"🔍 Raw data preview (bytes): {post_data[:500]}")
            raise Exception(f"Failed to parse multipart data: {str(e)}")
    
    def do_POST(self):
        request_id = str(uuid.uuid4())[:8]
        client_ip = self.client_address[0]
        
        logger.info(f"📥 POST request [{request_id}] from {client_ip} to: {self.path}")
        
        if self.path == '/upload':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                
                logger.info(f"🔍 [{request_id}] Data received: {len(post_data)} bytes")
                logger.info(f"📊 [{request_id}] Content-Type: {self.headers.get('Content-Type', 'Not specified')}")
                
                content_type = self.headers.get('Content-Type', '').lower()
                uploaded_files = []
                
                # Get upload directory
                script_dir = os.path.dirname(os.path.abspath(__file__))
                upload_dir = os.path.join(script_dir, 'received Files')
                os.makedirs(upload_dir, exist_ok=True)
                
                if 'application/json' in content_type:
                    logger.info(f"🔄 [{request_id}] Processing JSON upload")
                    
                    # Parse JSON
                    data = json.loads(post_data.decode('utf-8'))
                    content = data.get('file', '')
                    filename = data.get('filename', f'upload_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
                    encoding = data.get('encoding', 'text')
                    
                    # Sanitize filename but preserve original
                    original_filename = filename
                    filename = self.sanitize_filename(filename)
                    
                    logger.info(f"📝 [{request_id}] Original filename: '{original_filename}' -> Sanitized: '{filename}'")
                    
                    # Handle base64 encoding
                    if encoding == 'base64':
                        content_bytes = base64.b64decode(content)
                        file_info = self.get_file_info(filename, content_bytes)
                        
                        # Save file appropriately
                        filepath = os.path.join(upload_dir, filename)
                        filepath = self.ensure_unique_filename(filepath)
                        
                        with open(filepath, 'wb') as f:
                            f.write(content_bytes)
                        
                        file_size = len(content_bytes)
                        content_preview = f"<binary data: {file_size} bytes>"
                        
                    else:
                        # Text content
                        file_info = self.get_file_info(filename, content)
                        filepath = os.path.join(upload_dir, filename)
                        filepath = self.ensure_unique_filename(filepath)
                        
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        file_size = len(content.encode('utf-8'))
                        content_preview = content[:100] + "..." if len(content) > 100 else content
                    
                    uploaded_files.append({
                        'original_filename': original_filename,
                        'saved_filename': os.path.basename(filepath),
                        'size': file_size,
                        'path': filepath,
                        'file_info': file_info,
                        'content_preview': content_preview
                    })
                
                elif 'multipart/form-data' in content_type:
                    logger.info(f"🔄 [{request_id}] Processing multipart upload")
                    
                    # Extract boundary
                    boundary = None
                    for part in content_type.split(';'):
                        if 'boundary=' in part:
                            boundary = part.split('boundary=')[1].strip()
                            break
                    
                    if not boundary:
                        raise Exception("No boundary found in multipart data")
                    
                    logger.info(f"🔍 [{request_id}] Using boundary: {boundary}")
                    
                    # Parse multipart data
                    files_data = self.parse_multipart_data(post_data, boundary)
                    
                    for file_data in files_data:
                        original_filename = file_data['filename']
                        content = file_data['content']
                        
                        # Sanitize filename but preserve original
                        filename = self.sanitize_filename(original_filename)
                        
                        logger.info(f"📝 [{request_id}] Processing file: '{original_filename}' -> '{filename}'")
                        
                        # Get file info and save appropriately
                        file_info = self.get_file_info(filename, content)
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        upload_dir = os.path.join(script_dir, 'received Files')
                        filepath = os.path.join(upload_dir, filename)
                        filepath = self.ensure_unique_filename(filepath)
                        
                        # Save file based on type
                        if file_info['is_binary']:
                            with open(filepath, 'wb') as f:
                                f.write(content)
                            content_preview = f"<binary data: {len(content)} bytes>"
                        else:
                            try:
                                text_content = content.decode('utf-8')
                                with open(filepath, 'w', encoding='utf-8') as f:
                                    f.write(text_content)
                                content_preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                            except UnicodeDecodeError:
                                # Fallback to binary
                                with open(filepath, 'wb') as f:
                                    f.write(content)
                                content_preview = f"<binary data (decode failed): {len(content)} bytes>"
                        
                        uploaded_files.append({
                            'original_filename': original_filename,
                            'saved_filename': os.path.basename(filepath),
                            'size': len(content),
                            'path': filepath,
                            'file_info': file_info,
                            'content_preview': content_preview
                        })
                
                else:
                    logger.info(f"🔄 [{request_id}] Processing raw data upload")
                    
                    # Handle raw data
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f'raw_upload_{timestamp}.bin'
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    upload_dir = os.path.join(script_dir, 'received Files')
                    filepath = os.path.join(upload_dir, filename)
                    filepath = self.ensure_unique_filename(filepath)
                    
                    # Try to determine if it's text or binary
                    try:
                        text_content = post_data.decode('utf-8')
                        file_info = self.get_file_info(filename, text_content)
                        with open(filepath.replace('.bin', '.txt'), 'w', encoding='utf-8') as f:
                            f.write(text_content)
                        filepath = filepath.replace('.bin', '.txt')
                        content_preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                    except UnicodeDecodeError:
                        file_info = self.get_file_info(filename, post_data)
                        with open(filepath, 'wb') as f:
                            f.write(post_data)
                        content_preview = f"<binary data: {len(post_data)} bytes>"
                    
                    uploaded_files.append({
                        'original_filename': filename,
                        'saved_filename': os.path.basename(filepath),
                        'size': len(post_data),
                        'path': filepath,
                        'file_info': file_info,
                        'content_preview': content_preview
                    })
                
                # Log successful uploads
                for file_data in uploaded_files:
                    logger.info(f"✅ [{request_id}] File saved: '{file_data['original_filename']}' as '{file_data['saved_filename']}' ({file_data['size']} bytes, {file_data['file_info']['mime_type']})")
                
                # Prepare response
                response_data = {
                    'status': 'success',
                    'request_id': request_id,
                    'uploaded_files': [
                        {
                            'original_filename': f['original_filename'],
                            'saved_filename': f['saved_filename'],
                            'size': f['size'],
                            'mime_type': f['file_info']['mime_type'],
                            'is_binary': f['file_info']['is_binary'],
                            'hash': f['file_info']['hash'],
                            'download_url': f'https://up.datacenter-eg.site/files/{f["saved_filename"]}',
                            'content_preview': f['content_preview']
                        }
                        for f in uploaded_files
                    ],
                    'total_files': len(uploaded_files),
                    'total_size': sum(f['size'] for f in uploaded_files),
                    'timestamp': datetime.now().isoformat()
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('X-Request-ID', request_id)
                self.end_headers()
                self.wfile.write(json.dumps(response_data, indent=2).encode())
                
                logger.info(f"🎉 [{request_id}] Upload completed successfully: {len(uploaded_files)} files, {sum(f['size'] for f in uploaded_files)} total bytes")
                
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON: {str(e)}"
                logger.error(f"❌ [{request_id}] JSON Error: {error_msg}")
                
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('X-Request-ID', request_id)
                self.end_headers()
                error_response = {
                    'error': error_msg,
                    'request_id': request_id,
                    'received_bytes': len(post_data),
                    'content_type': self.headers.get('Content-Type', 'Unknown'),
                    'timestamp': datetime.now().isoformat()
                }
                self.wfile.write(json.dumps(error_response).encode())
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ [{request_id}] General Error: {error_msg}")
                
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('X-Request-ID', request_id)
                self.end_headers()
                error_response = {
                    'error': error_msg,
                    'request_id': request_id,
                    'timestamp': datetime.now().isoformat()
                }
                self.wfile.write(json.dumps(error_response).encode())
        
        elif self.path == '/status':
            # Server status endpoint
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                upload_dir = os.path.join(script_dir, 'received Files')
                files_count = len([f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))]) if os.path.exists(upload_dir) else 0
                
                status_data = {
                    'status': 'running',
                    'server': 'Advanced Upload Server',
                    'version': '1.0.0',
                    'timestamp': datetime.now().isoformat(),
                    'upload_directory': upload_dir,
                    'total_files': files_count,
                    'request_id': str(uuid.uuid4())[:8]
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(status_data, indent=2).encode())
                
                logger.info(f"📊 Status check from {client_ip}: {files_count} files in storage")
                
            except Exception as e:
                logger.error(f"❌ Status check error: {str(e)}")
                self.send_response(500)
                self.end_headers()

def main():
    PORT = 8787
    
    # Create upload directory in same directory as script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    upload_dir = os.path.join(script_dir, 'received Files')
    os.makedirs(upload_dir, exist_ok=True)
    
    logger.info("🚀 Starting Advanced HTTP Upload Server...")
    logger.info(f"📁 Upload directory: {upload_dir}")
    logger.info(f"🌐 Server will run on: https://up.datacenter-eg.site/")
    logger.info(f"📤 Upload endpoint: https://up.datacenter-eg.site/upload")
    logger.info(f"📊 Status endpoint: https://up.datacenter-eg.site/status")
    logger.info(f"📥 Download endpoint: https://up.datacenter-eg.site/files/<filename>")
    
    try:
        with socketserver.TCPServer(("0.0.0.0", PORT), AdvancedUploadHandler) as httpd:
            logger.info(f"✅ Advanced Upload Server is READY on port {PORT}")
            logger.info("🎯 Features: Original filename preservation, All file types, Advanced logging, File integrity checking")
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {str(e)}")

if __name__ == "__main__":
    main()
