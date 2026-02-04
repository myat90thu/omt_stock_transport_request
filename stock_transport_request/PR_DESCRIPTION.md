# Stock Transport Order Request — User Guide

Module: omt_stock_transport_request  
Description: Internal Stock Transport Order Request Between Different Warehouses

This user guide explains how to install, configure and use the Stock Transport Order Request (STO Request) module. It covers the new request lifecycle, approval rules scoped by providing warehouse, line-level "Free Qty", validation behaviour, and how pickings are created and confirmed.

---

## Table of contents

- Overview
- Key concepts
- Installation & upgrade notes
- Configuration
    - Warehouses: `Valid Request Qty`
    - Approval rules: `stock.transport.approval.rule`
    - Permissions & approver group
- Creating and managing Stock Transport Requests
    - Request form fields
    - Request lines
    - Actions & workflow
    - Example: request flow
- Picking lifecycle and automatic confirmation
- Validation rules and "Needs Revised Qty"
- Admin / Migration notes
- Troubleshooting & FAQ
- Contact / Next steps

---

## Overview

This module allows users to request stock transfers between warehouses inside Odoo. It enforces a simple, warehouse-scoped approval rule and a clear lifecycle:

- draft → requested → approved → confirmed

Important behaviours:
- Each request uses exactly one Providing Warehouse (the warehouse that supplies items) and one Requesting Warehouse (the receiver).
- Per-warehouse limits (`valid_qty`) prevent oversized requests. If requests exceed limits or line free-stock, the request is flagged as "Needs Revised Qty".
- Approval rules can be configured to auto-approve requests that meet limits.
- On approval, internal pickings and stock moves are created and an attempt to reserve stock is performed.
- When all linked pickings are completed (done), the request state becomes `confirmed`.

---

## Key concepts

- Requesting Warehouse: the receiving warehouse (destination of stock).
- Providing Warehouse: the supplying warehouse (source of stock). Each request must specify exactly one providing warehouse.
- Free Qty (per line): current available stock for the product in the providing warehouse (computed).
- valid_qty (approval rule): maximum allowed total quantity for requests coming from a specific providing warehouse. If present, it takes precedence over the warehouse fallback value.
- need_revision: boolean flag on the request indicating that one or more checks failed and the request needs changes.

---

## Installation & upgrade notes

1. Back up your database.
2. Place the module in your Odoo addons path.
3. Restart Odoo and update the Apps list.
4. Upgrade or install the module: `Stock Transport Order Request`.

---

## Configuration

### Warehouse: Valid Request Qty
A fallback field on each warehouse:

- Model: `stock.warehouse`
- Field: `valid_request_qty` (Float)
- Usage: Used only if no approval rule exists for the provided warehouse. If a rule exists, the rule's `valid_qty` takes precedence.

You can add `valid_request_qty` in Warehouse form (Inventory / Configuration / Warehouses). The module also adds this field to the warehouse list/tree view.

### Approval Rule: stock.transport.approval.rule
Create approval rules to control approval behaviour per providing warehouse.

Important fields:
- Name: rule name.
- Company: rule company.
- Providing Warehouse: `providing_warehouse_id` (required) — ties rule to a specific warehouse.
- Valid Request Qty: `valid_qty` (0 means no limit) — maximum allowed total quantity for requests. If > 0, requests with a total quantity above this will not pass the rule.
- Requires approval: `approve_required` (boolean) — true = manual approval required; false = rule allows auto-approval.
- Auto-create picking: `auto_create_picking` — used for auto-approval flows.
- Approver group: optional group to restrict who can approve.

Constraints:
- Only one approval rule per (company, providing_warehouse) is allowed. The module enforces a DB uniqueness constraint.

How the rules are evaluated:
- When a request is submitted, the module looks for a rule for the request's providing warehouse.
- If rule exists:
    - If total request qty > rule.valid_qty (and valid_qty > 0) → the rule does not match; the request will be flagged to need revision.
    - If rule matches and `approve_required=False` → the request will auto-approve.
    - If rule matches and `approve_required=True` → the request remains in `requested` and requires explicit approval.

If no rule exists, the module falls back to `providing_warehouse.valid_request_qty`.

---

## Permissions & approver group

- The module uses an optional approver group field on approval rules. Buttons in the UI are controlled by groups where appropriate. Server-side checks are present to prevent unauthorized approvals (action_approve enforces state and need_revision checks).
- Ensure approver users are in the proper Odoo group specified in the rule, or are granted the appropriate rights.

---

## Creating and managing Stock Transport Requests

Navigate to the module menu (depends on your menu setup). You will find views to create and manage STO Requests and Approval Rules.

### Request form fields (key ones)
- Request Reference: autogenerated sequence.
- Origin: source document (optional).
- Requesting Warehouse: the receiving warehouse (required).
- Providing Warehouse: the supplying warehouse (required).
- Requested By / Requested Date: metadata.
- Lines: one2many order lines for products, UoM and quantity.
- Pickings: link to created internal pickings (read-only).
- State: draft / requested / approved / confirmed / cancelled.
- Needs Revised Qty: boolean (readonly) — true when validation fails.

### Line fields
- Product: choose product.
- UoM: populated from product default UoM (onchange).
- Quantity: requested quantity (in selected UoM).
- Free Qty: readonly, computed quantity available in the providing warehouse (in product default UoM) — used for validation.

Important:
- UoM conversions: the module converts the requested quantity to the product's default UoM before comparing with Free Qty.

### Actions & workflow

Buttons available (typical visibility):

- Request (action_request)
    - Visible in `draft`.
    - Behaviour:
        - Validates presence of warehouses and at least one line.
        - Computes totals and checks:
            - Per-line requested qty (converted to product default UoM) ≤ product_free_qty?
            - Total request qty ≤ rule.valid_qty (if rule exists) or warehouse.valid_request_qty fallback?
        - If any check fails → state = `requested`, `need_revision` = True, message posted: which limits were exceeded.
        - If checks pass:
            - state = `requested`, `need_revision` = False.
            - If matching rule exists and `approve_required=False`, auto-approve is triggered (action_approve).

- Approve (action_approve)
    - Visible to approvers and only in `requested` when `need_revision == False`.
    - Behaviour:
        - Creates internal picking(s) with moves from providing → requesting warehouse (use their lot_stock_id locations).
        - Tries to confirm and assign the pickings (reservation attempt).
        - Links created pickings to the request and sets state = `approved`.
        - Posts message about approval and pickings created.

- Set to Draft (action_set_draft)
    - Moves a request back to `draft` and clears `need_revision`.

- Cancel (action_cancel)
    - Moves request to `cancelled`.

Automatic transition:
- When all linked pickings are done, the module sets request.state = `confirmed` and posts a message.

### Example workflow (typical)

1. User creates a request in `draft`:
     - Requesting Warehouse: WH-East
     - Providing Warehouse: WH-West
     - Lines: Product A, 10 units

2. User clicks **Request**:
     - Module finds an approval rule for WH-West with `valid_qty = 50` and `approve_required = True`.
     - Total 10 ≤ 50, Free Qty for Product A in WH-West is 20 → validations pass.
     - State becomes `requested`. Because `approve_required=True`, request remains awaiting approval.

3. Approver clicks **Approve**:
     - Module creates an internal picking and moves for Product A from WH-West → WH-East.
     - Module attempts to reserve (action_assign) so picking moves to reserved state if stock available.
     - State becomes `approved`.

4. Warehouse does transfer and finalizes the picking (picking state becomes `done`):
     - Module detects all linked pickings are done → request state is set to `confirmed`.

Edge case:
- If the request total was 60 (> rule.valid_qty=50), then on Request the request would be set to `requested` and `need_revision=True` with a message that totals exceed allowed limit; Approve is blocked until quantities are reduced.

---

## Picking lifecycle and automatic confirmation

- On approval, internal pickings are created with:
    - location_id = providing_warehouse.lot_stock_id
    - location_dest_id = requesting_warehouse.lot_stock_id
- The module calls `picking.action_confirm()` (if available) and `picking.action_assign()` to attempt reservation.
- The request is automatically set to `confirmed` when all linked pickings reach state `done`. Partial fulfillment is not considered confirmed — all linked pickings must be done.

---

## Validation rules and "Needs Revised Qty"

When the user clicks **Request**, the module runs these validations:

1. Presence of both warehouses and at least one line.
2. For each line:
     - Convert the requested quantity to the product's default UoM.
     - Compare with `product_free_qty` (qty_available in providing warehouse).
     - If requested_in_product_uom > product_free_qty → line violation.
3. Aggregate check:
     - If a rule exists for the providing warehouse → compare `total_qty` ≤ rule.valid_qty (if rule.valid_qty > 0).
     - If no rule exists → fallback to `providing_warehouse.valid_request_qty` (if set).
4. If any violation:
     - Request remains in `requested`, `need_revision = True`, and message lists violations.
     - Approve is blocked.
5. If no violations:
     - If rule exists and `approve_required=False` → auto-approve (picking created).
     - Otherwise remain `requested` for manual approval.

---

## Admin / Migration notes

- If your installation already has a different custom module or database schema changes, review and test the migration on a staging DB.
- The module enforces a uniqueness constraint on approval rules per (company, providing_warehouse_id). Creating a duplicate rule will raise an error.

---

## Troubleshooting & FAQ

Q: I clicked Request but the request was flagged `Needs Revised Qty`. What do I do?
- A: Read the message posted on the request: it will state whether the total exceeds the allowed limit or which lines exceed free stock. Edit the lines to reduce quantities or create a rule/adjust warehouse `valid_request_qty` if appropriate.

Q: Approve button is not visible or not working.
- A: Check that:
    - The request is in state `requested`.
    - `need_revision` is False.
    - Your user is in the approver group defined in the approval rule (or has necessary access rights).
    - Check server logs for server-side errors if you have permissions.

Q: Picking was created but not assigned / reserved.
  - The request is in state `requested`.
  - `need_revision` is False.
  - Your user is in the approver group defined in the approval rule (or has necessary access rights).
  - Check server logs for server-side errors if you have permissions.

Q: Picking was created but not assigned / reserved.
- A: The module attempts to assign the picking using the available standard Odoo methods (`action_confirm` / `action_assign`). If there's not enough stock, pickings remain in waiting or confirmed unassigned state. Investigate stock levels or review the Free Qty calculations.

Q: The DB rename failed on module upgrade.
- A: Restore DB from backup if needed. If rename failed, run the manual SQL rename:
  - `ALTER TABLE stock_transport_request RENAME COLUMN destination_warehouse_id TO providing_warehouse_id;`
  - Ensure you run this only if you know your DB state and have a backup.

Q: How to set up auto-approval?
- A: Create an approval rule for the providing warehouse with `approve_required = False` and set `valid_qty` appropriately. Requests within that limit will auto-approve on Request.

---