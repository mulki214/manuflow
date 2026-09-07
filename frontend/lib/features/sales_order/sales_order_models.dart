class SalesOrderItemModel {
  const SalesOrderItemModel({
    required this.id,
    required this.productCode,
    required this.partName,
    required this.partNo,
    required this.description,
    required this.quantityGrams,
    required this.unit,
    required this.materialReceivedQuantity,
    required this.outstandingMaterialQuantity,
    required this.deliveredQuantity,
    required this.outstandingOrderQuantity,
    required this.outstandingNote,
    required this.unitPrice,
    required this.amount,
    required this.remark,
    required this.wipQuantity,
    required this.finishGoodQuantity,
    required this.dispatchedQuantity,
  });

  factory SalesOrderItemModel.fromJson(Map<String, dynamic> json) {
    return SalesOrderItemModel(
      id: json['id'] as int,
      productCode: json['product_code'].toString(),
      partName: json['part_name'].toString(),
      partNo: json['part_no'].toString(),
      description: json['description'].toString(),
      quantityGrams: _number(json['quantity_grams']),
      unit: json['unit'].toString(),
      materialReceivedQuantity: _number(json['material_received_quantity']),
      outstandingMaterialQuantity: _number(
        json['outstanding_material_quantity'],
      ),
      deliveredQuantity: _number(json['delivered_quantity']),
      outstandingOrderQuantity: _number(json['outstanding_order_quantity']),
      outstandingNote: json['outstanding_note']?.toString() ?? '',
      unitPrice: _number(json['unit_price']),
      amount: _number(json['amount']),
      remark: json['remark']?.toString() ?? '',
      wipQuantity: _number(json['wip_quantity'] ?? 0),
      finishGoodQuantity: _number(json['finish_good_quantity'] ?? 0),
      dispatchedQuantity: _number(json['dispatched_quantity'] ?? 0),
    );
  }

  final int id;
  final String productCode;
  final String partName;
  final String partNo;
  final String description;
  final double quantityGrams;
  final String unit;
  final double materialReceivedQuantity;
  final double outstandingMaterialQuantity;
  final double deliveredQuantity;
  final double outstandingOrderQuantity;
  final String outstandingNote;
  final double unitPrice;
  final double amount;
  final String remark;
  final double wipQuantity;
  final double finishGoodQuantity;
  final double dispatchedQuantity;
}

class SalesOrderModel {
  const SalesOrderModel({
    required this.salesOrderNumber,
    required this.poReceiptDate,
    required this.customerPoDate,
    required this.customerPoNumber,
    required this.customerCode,
    required this.customerName,
    required this.billToAddress,
    required this.billToPhone,
    required this.shipToName,
    required this.shipToAddress,
    required this.shipToContactPerson,
    required this.shipToPhone,
    required this.deliveryDate,
    required this.orderType,
    required this.notes,
    required this.grandTotal,
    required this.status,
    required this.fulfillmentStatus,
    required this.createdByName,
    required this.reviewedByName,
    required this.rejectionReason,
    required this.canEdit,
    required this.canDelete,
    required this.canReview,
    required this.creatorQrPayload,
    required this.approvalQrPayload,
    required this.items,
  });

  factory SalesOrderModel.fromJson(Map<String, dynamic> json) {
    return SalesOrderModel(
      salesOrderNumber: json['sales_order_number'].toString(),
      poReceiptDate: DateTime.parse(json['po_receipt_date'].toString()),
      customerPoDate: DateTime.parse(json['customer_po_date'].toString()),
      customerPoNumber: json['customer_po_number'].toString(),
      customerCode: json['customer_code'].toString(),
      customerName: json['customer_name'].toString(),
      billToAddress: json['bill_to_address'].toString(),
      billToPhone: json['bill_to_phone'].toString(),
      shipToName: json['ship_to_name'].toString(),
      shipToAddress: json['ship_to_address'].toString(),
      shipToContactPerson: json['ship_to_contact_person'].toString(),
      shipToPhone: json['ship_to_phone'].toString(),
      deliveryDate: DateTime.parse(json['delivery_date'].toString()),
      orderType: json['order_type'].toString(),
      notes: json['notes']?.toString() ?? '',
      grandTotal: _number(json['grand_total']),
      status: json['status'].toString(),
      fulfillmentStatus: json['fulfillment_status'].toString(),
      createdByName: json['created_by_name'].toString(),
      reviewedByName: json['reviewed_by_name']?.toString(),
      rejectionReason: json['rejection_reason']?.toString(),
      canEdit: json['can_edit'] == true,
      canDelete: json['can_delete'] == true,
      canReview: json['can_review'] == true,
      creatorQrPayload: json['creator_qr_payload'].toString(),
      approvalQrPayload: json['approval_qr_payload']?.toString(),
      items: (json['items'] as List)
          .map(
            (item) =>
                SalesOrderItemModel.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
    );
  }

  final String salesOrderNumber;
  final DateTime poReceiptDate;
  final DateTime customerPoDate;
  final String customerPoNumber;
  final String customerCode;
  final String customerName;
  final String billToAddress;
  final String billToPhone;
  final String shipToName;
  final String shipToAddress;
  final String shipToContactPerson;
  final String shipToPhone;
  final DateTime deliveryDate;
  final String orderType;
  final String notes;
  final double grandTotal;
  final String status;
  final String fulfillmentStatus;
  final String createdByName;
  final String? reviewedByName;
  final String? rejectionReason;
  final bool canEdit;
  final bool canDelete;
  final bool canReview;
  final String creatorQrPayload;
  final String? approvalQrPayload;
  final List<SalesOrderItemModel> items;

  String get descriptions => items.map((item) => item.description).join(', ');
  String get quantitySummary => _unitSummary(
    items.map((item) => (unit: item.unit, quantity: item.quantityGrams)),
  );
}

String _unitSummary(Iterable<({String unit, double quantity})> values) {
  final totals = <String, double>{};
  for (final value in values) {
    totals[value.unit] = (totals[value.unit] ?? 0) + value.quantity;
  }
  return totals.entries
      .map((entry) => '${_plainNumber(entry.value)} ${entry.key}')
      .join(' • ');
}

String _plainNumber(double value) =>
    value.toStringAsFixed(3).replaceFirst(RegExp(r'\.?0+$'), '');

double _number(dynamic value) => double.parse(value.toString());

String salesOrderStatusLabel(String status) => switch (status) {
  'waiting_review' => 'Waiting Review',
  'approved' => 'Approved',
  'rejected' => 'Rejected',
  _ => status,
};

String salesOrderTypeLabel(String type) => switch (type) {
  'mass_pro' => 'Mass Production',
  'job_order' => 'Job Order',
  'trial' => 'Trial',
  _ => type,
};
