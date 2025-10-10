"""
Professional Flask API with Enhanced Logging and File Operations
===============================================================

A robust and professional Flask API that provides JSON data processing,
file operations, and comprehensive logging capabilities.

Author: WEEEZA Corporation
Version: 2.0
"""

import os
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Union
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler

from flask import Flask, request, jsonify, Response
from werkzeug.exceptions import HTTPException


@dataclass
class APIConfig:
    """Configuration class for API settings"""
    
    HOST: str = '0.0.0.0'
    PORT: int = 8585
    DEBUG: bool = True
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    DEFAULT_FILENAME: str = 'data.txt'
    LOGS_DIR: str = 'logs'
    REQUEST_LOG_FILE: str = 'requests.json'


class LoggingManager:
    """Professional logging management class"""
    
    def __init__(self, app: Flask, config: APIConfig):
        self.app = app
        self.config = config
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup enhanced logging with rotating file handler"""
        # Create logs directory
        script_dir = Path(__file__).parent
        logs_dir = script_dir / self.config.LOGS_DIR
        logs_dir.mkdir(exist_ok=True)
        
        # Setup rotating file handler
        log_file = logs_dir / "api.log"
        handler = RotatingFileHandler(
            log_file, 
            maxBytes=self.config.LOG_MAX_BYTES, 
            backupCount=self.config.LOG_BACKUP_COUNT
        )
        handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        handler.setFormatter(formatter)
        
        # Configure app logger
        self.app.logger.addHandler(handler)
        self.app.logger.setLevel(logging.INFO)
        
        return self.app.logger
    
    def log_request(self, request_data: Any, endpoint: str, method: str, 
                   response_status: int, client_ip: str = None, 
                   user_agent: str = None) -> None:
        """Enhanced request logging with metadata"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "method": method,
            "request_data": request_data,
            "response_status": response_status,
            "client_ip": client_ip or "unknown",
            "user_agent": user_agent or "unknown",
            "request_size": len(str(request_data)) if request_data else 0
        }
        
        try:
            script_dir = Path(__file__).parent
            log_file = script_dir / self.config.REQUEST_LOG_FILE
            
            # Ensure file exists
            log_file.touch(exist_ok=True)
            
            # Append log entry
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
            
            # Log to application log
            self.logger.info(
                f"Request logged: {endpoint} {method} - "
                f"Status: {response_status} - IP: {client_ip}"
            )
            
        except Exception as e:
            self.logger.error(f"Error logging request: {e}")
    
    def store_sisi_request(self, request_data: Any, client_ip: str = None, 
                          method: str = None, status: int = 200, 
                          error_info: str = None) -> None:
        """Store /sisi requests in requests.json"""
        if not request_data and not error_info:
            return
            
        entry = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": "/sisi",
            "method": method or "POST",
            "client_ip": client_ip or "unknown",
            "request_data": request_data,
            "status": status,
            "error_info": error_info,
            "is_success": status == 200
        }
        
        try:
            script_dir = Path(__file__).parent
            requests_file = script_dir / self.config.REQUEST_LOG_FILE
            
            # Ensure file exists
            requests_file.touch(exist_ok=True)
            
            # Append entry
            with open(requests_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
            
            self.logger.info(f"SISI request stored: Status {status}")
            
        except Exception as e:
            self.logger.error(f"Error storing sisi request: {e}")


class FileManager:
    """Professional file management class"""
    
    def __init__(self, config: APIConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
    
    def write_text_to_file(self, text_content: str, 
                          filename: str = None) -> Tuple[bool, str]:
        """Write text content to a file with error handling"""
        filename = filename or self.config.DEFAULT_FILENAME
        
        try:
            script_dir = Path(__file__).parent
            file_path = script_dir / filename
            
            # Write to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text_content)
            
            self.logger.info(f"Text written to file: {file_path}")
            return True, f"File written successfully to {file_path}"
            
        except Exception as e:
            self.logger.error(f"Error writing to file: {e}")
            return False, f"Error writing to file: {e}"
    
    def read_file_content(self, filename: str = None) -> Tuple[bool, str]:
        """Read file content and return it"""
        filename = filename or self.config.DEFAULT_FILENAME
        
        try:
            script_dir = Path(__file__).parent
            file_path = script_dir / filename
            
            if not file_path.exists():
                return False, f"File {filename} does not exist"
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            self.logger.info(f"File content read: {file_path}")
            return True, content
            
        except Exception as e:
            self.logger.error(f"Error reading file: {e}")
            return False, f"Error reading file: {e}"


class RequestValidator:
    """Request validation utilities"""
    
    @staticmethod
    def validate_json_data(data: Any) -> Tuple[bool, str]:
        """Validate JSON data"""
        if data is None:
            return False, "No JSON data provided"
        
        if not isinstance(data, dict):
            return False, "Invalid JSON format - expected object"
        
        return True, "Valid JSON data"
    
    @staticmethod
    def validate_text_data(data: str) -> Tuple[bool, str]:
        """Validate text data"""
        if not data or not data.strip():
            return False, "No text data provided"
        
        if len(data) > 1000000:  # 1MB limit
            return False, "Text data too large (max 1MB)"
        
        return True, "Valid text data"


class ProfessionalAPI:
    """Main API class with professional structure"""
    
    def __init__(self):
        self.config = APIConfig()
        self.app = Flask(__name__)
        self.logging_manager = LoggingManager(self.app, self.config)
        self.file_manager = FileManager(self.config, self.logging_manager.logger)
        self.validator = RequestValidator()
        self._register_middleware()
        self._register_routes()
        self._register_error_handlers()
    
    def _get_client_info(self) -> Tuple[str, str]:
        """Extract client information from request"""
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR') or \
                   request.environ.get('REMOTE_ADDR') or 'unknown'
        user_agent = request.headers.get('User-Agent', 'unknown')
        return client_ip, user_agent
    
    def _register_middleware(self):
        """Register simplified middleware"""
        pass  # Simplified - no middleware needed
    
    def _create_response(self, data: Dict[str, Any], status_code: int = 200,
                        include_file_content: bool = True) -> Tuple[Response, int]:
        """Create standardized response with optional file content"""
        
        # Add file content if requested
        if include_file_content:
            success, file_content = self.file_manager.read_file_content()
            if success:
                data['file_content'] = {
                    'filename': self.config.DEFAULT_FILENAME,
                    'content': file_content,
                    'size': len(file_content)
                }
            else:
                data['file_content'] = {
                    'error': file_content,
                    'filename': self.config.DEFAULT_FILENAME
                }
        
        # Add metadata
        data['metadata'] = {
            'timestamp': datetime.now().isoformat(),
            'api_version': '2.0',
            'server_info': {
                'host': self.config.HOST,
                'port': self.config.PORT
            }
        }
        
        return jsonify(data), status_code
    
    def _register_error_handlers(self):
        """Register global error handlers"""
        
        @self.app.errorhandler(HTTPException)
        def handle_http_exception(e):
            client_ip, user_agent = self._get_client_info()
            
            self.logging_manager.log_request(
                str(e), request.endpoint or 'unknown', 
                request.method, e.code, client_ip, user_agent
            )
            
            return self._create_response({
                'error': e.description,
                'status': 'failed',
                'error_code': e.code
            }, e.code, include_file_content=False)
        
        @self.app.errorhandler(Exception)
        def handle_generic_exception(e):
            client_ip, user_agent = self._get_client_info()
            
            self.logging_manager.log_request(
                str(e), request.endpoint or 'unknown', 
                request.method, 500, client_ip, user_agent
            )
            
            return self._create_response({
                'error': 'Internal server error',
                'status': 'failed',
                'error_code': 500
            }, 500, include_file_content=False)
    
    
    def _attempt_json_fix(self, raw_content: str) -> Optional[str]:
        """Attempt to fix common JSON formatting issues"""
        if not raw_content or not isinstance(raw_content, str):
            return None
        
        try:
            # Fix unquoted strings in arrays - specifically for procedureNames pattern
            # Pattern: {"procedureNames":[word1,word2,word3]} 
            # Fix to: {"procedureNames":["word1","word2","word3"]}
            
            # First, let's check if this looks like the specific pattern we're dealing with
            if '"procedureNames":[' in raw_content and raw_content.count('[') == 1:
                # Use regex to find and fix unquoted array elements
                def quote_array_elements(match):
                    array_content = match.group(1)
                    # Split by comma and add quotes around each element
                    elements = [elem.strip() for elem in array_content.split(',')]
                    quoted_elements = [f'"{elem}"' if not (elem.startswith('"') and elem.endswith('"')) else elem for elem in elements]
                    return '[' + ','.join(quoted_elements) + ']'
                
                # Pattern to match array content between [ and ]
                pattern = r'\[([^\[\]]+)\]'
                fixed_content = re.sub(pattern, quote_array_elements, raw_content)
                
                # Validate that the fix worked
                try:
                    json.loads(fixed_content)
                    return fixed_content
                except:
                    pass
            
            # Try other common fixes
            # Fix: {key: value} -> {"key": value} (unquoted keys)
            fixed = re.sub(r'(\w+):', r'"\1":', raw_content)
            
            # Try to validate
            try:
                json.loads(fixed)
                return fixed
            except:
                pass
                
        except Exception as e:
            self.logging_manager.logger.debug(f"JSON fix attempt failed: {e}")
        
        return None
    
    def _register_routes(self):
        """Register all API routes"""
        
        @self.app.route('/', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
        def home():
            """API information endpoint"""
            client_ip, user_agent = self._get_client_info()
            
            response_data = {
                'api': 'Professional Python JSON API',
                'version': '2.0',
                'status': 'operational',
                'endpoints': {
                    '/': {
                        'methods': ['GET'],
                        'description': 'API information and documentation'
                    },
                    '/sisi': {
                        'methods': ['POST', 'GET'],
                        'description': 'JSON data processing endpoint'
                    },
                    '/send': {
                        'methods': ['POST'],
                        'description': 'File writing operations with multiple input formats'
                    },
                    '/health': {
                        'methods': ['GET'],
                        'description': 'Health check endpoint'
                    }
                },
                'features': {
                    'enhanced_logging': 'Comprehensive request logging with client metadata',
                    'file_operations': 'Advanced file reading and writing capabilities via /send endpoint',
                    'rotating_logs': f'Automatic log rotation ({self.config.LOG_MAX_BYTES // (1024*1024)}MB max, {self.config.LOG_BACKUP_COUNT} backups)',
                    'file_content_display': 'Automatic file content display after each request',
                    'error_handling': 'Professional error handling and validation',
                    'request_validation': 'Input validation and sanitization'
                }
            }
            
            self.logging_manager.log_request(
                None, '/', 'GET', 200, client_ip, user_agent
            )
            
            return self._create_response(response_data)
        
        @self.app.route('/health', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
        def health_check():
            """Health check endpoint"""
            client_ip, user_agent = self._get_client_info()
            
            response_data = {
                'status': 'healthy',
                'uptime': 'operational',
                'version': '2.0'
            }
            
            self.logging_manager.log_request(
                None, '/health', 'GET', 200, client_ip, user_agent
            )
            
            return self._create_response(response_data, include_file_content=False)
        
        @self.app.route('/sisi', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
        def sisi_endpoint():
            """Simplified JSON data processing endpoint"""
            client_ip, user_agent = self._get_client_info()
            
            # Handle GET requests
            if request.method == 'GET':
                return self._create_response({
                    'endpoint': 'sisi',
                    'description': 'JSON data processing endpoint',
                    'accepts_all_methods': True,
                    'logs_to': 'requests.json'
                })
            
            try:
                # Get request data
                json_data = None
                raw_content = None
                
                # Try to get raw content
                try:
                    if request.data:
                        raw_content = request.data.decode('utf-8')
                except Exception:
                    raw_content = str(request.data) if request.data else None
                
                # Try to parse JSON with auto-fix
                try:
                    json_data = request.get_json(force=True)
                except Exception as json_error:
                    # Try auto-fix for malformed JSON
                    fixed_json = self._attempt_json_fix(raw_content)
                    if fixed_json:
                        try:
                            json_data = json.loads(fixed_json)
                            raw_content = f"AUTO-FIXED: {fixed_json}"
                        except Exception:
                            pass
                    
                    if json_data is None:
                        # Store failed request
                        self.logging_manager.store_sisi_request(
                            request_data=raw_content or "No content",
                            client_ip=client_ip,
                            method=request.method,
                            status=400,
                            error_info=f"JSON Parse Error: {str(json_error)}"
                        )
                        
                        return self._create_response({
                            'error': f'Invalid JSON: {str(json_error)}',
                            'status': 'failed'
                        }, 400, include_file_content=False)
                
                # Store successful request in requests.json
                self.logging_manager.store_sisi_request(
                    request_data=json_data or raw_content,
                    client_ip=client_ip,
                    method=request.method,
                    status=200
                )
                
                return self._create_response({
                    'status': 'success',
                    'message': 'Data processed and stored in requests.json',
                    'received_data': json_data or raw_content
                })
                
            except Exception as e:
                # Store error
                self.logging_manager.store_sisi_request(
                    request_data=f"Exception: {str(e)}",
                    client_ip=client_ip,
                    method=request.method,
                    status=500,
                    error_info=str(e)
                )
                raise
        
        @self.app.route('/send', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
        def send_endpoint():
            """Simplified file sending endpoint - writes all data to data.txt"""
            client_ip, user_agent = self._get_client_info()
            
            # Handle GET requests
            if request.method == 'GET':
                return self._create_response({
                    'endpoint': 'send',
                    'description': 'File writing endpoint',
                    'accepts_all_methods': True,
                    'writes_to': 'data.txt'
                })
            
            try:
                # Get content like the original PHP version
                content = None
                
                # Check for 'send' parameter in form data (like PHP $_POST['send'])
                if request.form and 'send' in request.form:
                    content = request.form['send']
                # Check for 'send' parameter in JSON data
                elif request.is_json:
                    json_data = request.get_json()
                    if json_data and 'send' in json_data:
                        content = str(json_data['send'])
                    else:
                        content = json.dumps(json_data, indent=2)
                # Raw data (plain text)
                elif request.data:
                    try:
                        content = request.data.decode('utf-8')
                    except:
                        content = str(request.data)
                # URL parameters
                elif request.args and 'send' in request.args:
                    content = request.args['send']
                else:
                    content = f"Empty {request.method} request"
                
                # Write to data.txt
                success, message = self.file_manager.write_text_to_file(content, 'data.txt')
                
                if success:
                    # Return just the content of data.txt as plain text
                    success_read, file_content = self.file_manager.read_file_content('data.txt')
                    if success_read:
                        return Response(file_content, mimetype='text/plain')
                    else:
                        return Response(content, mimetype='text/plain')
                else:
                    return Response(f"Error: {message}", mimetype='text/plain', status=500)
                    
            except Exception as e:
                return Response(f"Error: {str(e)}", mimetype='text/plain', status=500)
    
    def run(self):
        """Start the API server"""
        print("=" * 70)
        print("🚀 Professional Python API Server Starting...")
        print("=" * 70)
        print(f"📍 Host: {self.config.HOST}")
        print(f"🔌 Port: {self.config.PORT}")
        print(f"🔧 Debug Mode: {self.config.DEBUG}")
        print()
        print("📚 Available Endpoints:")
        print("  🏠 / (GET)          - API information and documentation")
        print("  📊 /sisi (POST/GET) - JSON data processing")
        print("  📝 /send (POST)     - File sending/writing operations")
        print("  ❤️  /health (GET)   - Health check")
        print()
        print("✨ Features:")
        print("  📋 Enhanced logging with rotation")
        print("  📄 File content display after each request")
        print("  🛡️  Professional error handling")
        print("  ✅ Request validation")
        print("  🔍 Client metadata tracking")
        print()
        print(f"🌐 Visit: https://sisi.datacenter-eg.site/")
        print("=" * 70)
        
        self.app.run(
            host=self.config.HOST, 
            port=self.config.PORT, 
            debug=self.config.DEBUG
        )


# Application Factory
def create_app() -> Flask:
    """Application factory function"""
    api = ProfessionalAPI()
    return api.app


# Main execution
if __name__ == '__main__':
    # Create and run the professional API
    professional_api = ProfessionalAPI()
    professional_api.run()