import 'package:erp_manufaktur/features/sales_order/sales_order_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('sales order maps wireframe list summaries and permissions', () {
    final order = SalesOrderModel.fromJson({
      'sales_order_number': 'SO-130826-000',
      'po_receipt_date': '2026-08-13',
      'customer_po_date': '2026-08-12',
      'customer_po_number': 'CPO-001',
      'customer_code': 'CUS',
      'customer_name': 'Customer Example',
      'bill_to_address': 'Jakarta',
      'bill_to_phone': '021123',
      'ship_to_name': 'Customer Warehouse',
      'ship_to_address': 'Bekasi',
      'ship_to_contact_person': 'Andi',
      'ship_to_phone': '08123',
      'delivery_date': '2026-08-20',
      'order_type': 'mass_pro',
      'notes': '',
      'grand_total': '2555.50',
      'status': 'waiting_review',
      'fulfillment_status': 'open',
      'created_by_name': 'Sales PIC',
      'reviewed_by_name': null,
      'rejection_reason': null,
      'can_edit': true,
      'can_delete': true,
      'can_review': false,
      'creator_qr_payload': 'creator-token',
      'approval_qr_payload': null,
      'items': [
        {
          'id': 1,
          'product_code': 'PRD',
          'part_name': 'Steel Plate',
          'part_no': 'SP-01',
          'description': 'Steel Plate SP-01',
          'quantity_grams': '1000.000',
          'unit': 'bar',
          'material_received_quantity': '400.000',
          'outstanding_material_quantity': '600.000',
          'delivered_quantity': '250.000',
          'outstanding_order_quantity': '750.000',
          'outstanding_note': 'Waiting material',
          'unit_price': '2.5555',
          'amount': '2555.50',
          'remark': '',
        },
      ],
    });

    expect(order.salesOrderNumber, 'SO-130826-000');
    expect(order.descriptions, 'Steel Plate SP-01');
    expect(order.quantitySummary, '1000 bar');
    expect(order.items.first.outstandingMaterialQuantity, 600);
    expect(order.canEdit, isTrue);
    expect(salesOrderStatusLabel(order.status), 'Waiting Review');
    expect(salesOrderTypeLabel(order.orderType), 'Mass Production');
  });
}
