# Stock Transport Request Module - Version 2.0.0

## Overview
This module provides comprehensive Stock Transport Order (STO) Request management with dynamic approval rules, warehouse quantity validation, and automated picking creation.

## Features

### Request Lifecycle
- **Draft**: Initial state for creating and editing requests
- **Requested**: Submitted for validation and approval
- **Approved**: Approved and pickings created
- **Confirmed**: All pickings completed successfully
- **Cancelled**: Request cancelled

### Approval Rules
- Configure rules per providing warehouse
- Set valid quantity limits per warehouse
- Automatic approval for requests within limits
- Group-based approval authorization
- Fallback to warehouse-level limits if no rule matches

### Validation
- Real-time product availability checking
- UoM conversion for accurate quantity comparison
- Per-line free quantity display
- Automatic need_revision flagging for over-limit requests

### Picking Management
- Automatic internal picking creation on approval
- Link between requests and pickings
- Automatic confirmation when all pickings are done
- Stock reservation attempts

## Installation

1. Place module in your Odoo addons directory
2. Update apps list
3. Install "Stock Transport Order Request"
4. Configure warehouses with valid_request_qty
5. Create approval rules as needed

## Configuration

### Warehouse Configuration
Navigate to: Inventory > Configuration > Warehouses

Set `Valid Request Qty` for each warehouse to define the maximum total quantity allowed for requests.

### Approval Rules
Navigate to: STO Requests > Approval Rules

Create rules with:
- **Providing Warehouse**: Source warehouse for requests
- **Valid Request Qty**: Maximum allowed quantity (0 = no limit)
- **Requires Approval**: If unchecked, auto-approves matching requests
- **Approver Group**: Group authorized to approve

## Usage

### Creating a Request

1. Navigate to: STO Requests > Requests
2. Click "Create"
3. Select **Requesting Warehouse** (receiver)
4. Select **Providing Warehouse** (supplier)
5. Add product lines with quantities
6. View **Free Qty** column for availability
7. Click **Request** to submit

### Approval Process

If need_revision is True:
- Review warning message
- Adjust quantities
- Resubmit request

If need_revision is False:
- Authorized users click **Approve**
- Pickings are created automatically
- Request moves to Approved state

### Completion

When warehouse staff completes all pickings:
- Request automatically moves to Confirmed state
- No manual intervention needed

## Technical Details

### Database Migration
When upgrading from version 1.x:
- `destination_warehouse_id` is automatically renamed to `providing_warehouse_id`
- All existing data is preserved
- Migration is logged for verification

### UoM Conversion
The module properly handles different units of measure:
```python
requested_qty_in_product_uom = line.product_uom_id._compute_quantity(
    line.product_uom_qty, 
    line.product_id.uom_id
)
```

### Auto-Confirmation Hook
A write hook on `stock.picking` monitors picking completion:
```python
def write(self, vals):
    result = super().write(vals)
    if 'state' in vals:
        requests = self.mapped('transport_request_id')
        for request in requests:
            request._check_and_confirm()
    return result
```

## Version History

### Version 2.0.0 (Current)
- Renamed destination_warehouse_id to providing_warehouse_id
- Simplified approval rules (removed min/max qty and value)
- New request lifecycle (draft → requested → approved → confirmed)
- Added need_revision flag for over-limit handling
- Product free quantity display in lines
- UoM conversion for accurate comparisons
- Warehouse-level valid_request_qty field
- Automatic confirmation on picking completion
- Smart button to view related pickings

### Version 1.0.0
- Initial release with basic STO request functionality

## Support
For issues or questions, please contact the module author or submit an issue on GitHub.

## License
LGPL-3

## Author
Max Thu - Odoo Myanmar Tutorial
