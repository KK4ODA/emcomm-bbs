"""
Welfare Board - Validator Module
Validates parsed welfare check-in data against requirements
"""

import re
from datetime import datetime


class WelfareValidator:
    """Validate welfare check-in data"""
    
    # Valid callsign pattern (US amateur radio)
    CALLSIGN_PATTERN = r'^[A-Z]{1,2}[0-9][A-Z]{1,4}$'
    
    # Valid status values
    VALID_STATUSES = ['SAFE', 'NEED ASSISTANCE', 'TRAFFIC']
    
    # Basic phone pattern (digits, dashes, spaces, parens, plus sign; at least 7 digits)
    PHONE_PATTERN = r'^[\+]?[\d\s\-\(\)\.]{7,20}$'
    
    # Basic email pattern
    EMAIL_PATTERN = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
    
    def __init__(self, config=None):
        """
        Initialize validator
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        
        # Get validation rules from config
        validation_config = self.config.get('validation', {})
        self.require_callsign = validation_config.get('require_callsign', True)
        self.require_name = validation_config.get('require_name', True)
        self.require_location = validation_config.get('require_location', True)
        self.require_status = validation_config.get('require_status', True)
        self.valid_statuses = validation_config.get('valid_statuses', self.VALID_STATUSES)
    
    def validate(self, parsed_data):
        """
        Validate parsed welfare check-in data.
        
        Non-ham operators may check in using just their name (no callsign).
        If callsign is missing, NAME becomes required as the identifier.
        
        Args:
            parsed_data: Dictionary from parser
            
        Returns:
            tuple: (is_valid, errors)
                is_valid (bool): True if data is valid
                errors (list): List of error messages
        """
        errors = []
        
        if not parsed_data:
            errors.append("No data to validate")
            return False, errors
        
        has_callsign = bool(parsed_data.get('callsign'))
        has_name = bool(parsed_data.get('name'))
        
        # Validate identity: need at least a callsign OR a name
        if has_callsign:
            # If a callsign is provided, validate its format
            callsign_valid, callsign_errors = self.validate_callsign(parsed_data.get('callsign'))
            if not callsign_valid:
                errors.extend(callsign_errors)
        
        if not has_callsign and not has_name:
            errors.append("Either CALLSIGN or NAME is required to identify the person checking in")
        elif not has_callsign and has_name:
            # Non-ham check-in by name only - this is valid
            # Assign a generated identifier for internal tracking
            pass
        
        # NAME is always required (even hams should provide their name)
        if self.require_name and not has_name:
            errors.append("NAME field is required but missing or empty")
        
        if self.require_location:
            if not parsed_data.get('location'):
                errors.append("LOCATION field is required but missing or empty")
        
        if self.require_status:
            status_valid, status_errors = self.validate_status(parsed_data.get('status'))
            if not status_valid:
                errors.extend(status_errors)
        
        # Validate contact field if provided (optional but checked for format)
        contact = parsed_data.get('contact')
        if contact:
            contact_valid, contact_errors = self.validate_contact(contact)
            if not contact_valid:
                errors.extend(contact_errors)
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_callsign(self, callsign):
        """
        Validate callsign format
        
        Args:
            callsign: Callsign string to validate
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        if not callsign:
            errors.append("CALLSIGN field is required but missing or empty")
            return False, errors
        
        # Remove whitespace and convert to uppercase
        callsign = callsign.strip().upper()
        
        # Check format
        if not re.match(self.CALLSIGN_PATTERN, callsign):
            errors.append(f"CALLSIGN '{callsign}' does not match valid amateur radio callsign format")
        
        # Check length
        if len(callsign) < 3 or len(callsign) > 7:
            errors.append(f"CALLSIGN '{callsign}' length must be between 3 and 7 characters")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_status(self, status):
        """
        Validate status field
        
        Args:
            status: Status string to validate
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        if not status:
            errors.append("STATUS field is required but missing or empty")
            return False, errors
        
        # Normalize status
        status_upper = status.upper().strip()
        
        # Check if it's one of the valid statuses
        if status_upper not in self.valid_statuses:
            valid_list = ', '.join(self.valid_statuses)
            errors.append(f"STATUS '{status}' is not valid. Must be one of: {valid_list}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_contact(self, contact):
        """
        Validate contact field (phone number for SMS or email address)
        
        Args:
            contact: Contact string to validate
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        if not contact:
            return True, errors  # Contact is optional
        
        contact = contact.strip()
        
        # Check if it looks like a phone number or an email
        is_phone = re.match(self.PHONE_PATTERN, contact)
        is_email = re.match(self.EMAIL_PATTERN, contact, re.IGNORECASE)
        
        if not is_phone and not is_email:
            errors.append(f"CONTACT '{contact}' does not appear to be a valid phone number or email address")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def check_duplicate(self, parsed_data, existing_checkins):
        """
        Check if this is a duplicate check-in
        
        Uses callsign as primary identifier, falls back to name for non-ham check-ins.
        
        Args:
            parsed_data: New check-in data
            existing_checkins: List of existing check-ins for this window
            
        Returns:
            tuple: (is_duplicate, message)
        """
        if not parsed_data or not existing_checkins:
            return False, None
        
        identifier = self._get_identifier(parsed_data)
        
        for existing in existing_checkins:
            existing_id = self._get_identifier(existing)
            if existing_id == identifier:
                return True, f"Duplicate check-in: {identifier} already checked in for this time window"
        
        return False, None
    
    @staticmethod
    def _get_identifier(checkin_data):
        """
        Get the unique identifier for a check-in.
        Uses callsign if available, otherwise uses NAME (uppercased).
        
        Args:
            checkin_data: Check-in dictionary
            
        Returns:
            str: Identifier string
        """
        callsign = checkin_data.get('callsign', '').strip().upper()
        if callsign:
            return callsign
        name = checkin_data.get('name', '').strip().upper()
        return f"NAME:{name}" if name else "UNKNOWN"
    
    def validate_file_format(self, content):
        """
        Quick validation of file format before full parsing
        
        Args:
            content: File content string
            
        Returns:
            tuple: (is_valid, message)
        """
        if not content or not content.strip():
            return False, "File is empty"
        
        # Check for required field headers - CALLSIGN is optional for non-hams,
        # but NAME is always required
        required_headers = ['NAME:', 'LOCATION:', 'STATUS:']
        optional_headers = ['CALLSIGN:']  # Nice to have but not required
        missing_headers = []
        
        content_upper = content.upper()
        for header in required_headers:
            if header not in content_upper:
                missing_headers.append(header)
        
        if missing_headers:
            return False, f"Missing required field(s): {', '.join(missing_headers)}"
        
        return True, "Format looks valid"
    
    def create_validation_report(self, parsed_data, is_valid, errors):
        """
        Create a formatted validation report
        
        Args:
            parsed_data: The data that was validated
            is_valid: Whether validation passed
            errors: List of validation errors
            
        Returns:
            str: Formatted report
        """
        report = []
        report.append("=" * 60)
        report.append("VALIDATION REPORT")
        report.append("=" * 60)
        
        if parsed_data:
            report.append(f"File: {parsed_data.get('filename', 'Unknown')}")
            report.append(f"Callsign: {parsed_data.get('callsign', 'N/A')}")
            report.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        report.append("")
        
        if is_valid:
            report.append("✓ VALIDATION PASSED")
            report.append("All required fields present and valid")
        else:
            report.append("✗ VALIDATION FAILED")
            report.append("")
            report.append("Errors found:")
            for i, error in enumerate(errors, 1):
                report.append(f"  {i}. {error}")
        
        report.append("=" * 60)
        
        return '\n'.join(report)

