class PurchaseOrderItemModel {
  const PurchaseOrderItemModel({
    required this.id,
    required this.productCode,
    required this.partName,
    required this.partNo,
    required this.description,
    required this.quantityGrams,
    required this.unit,
    required this.receivedQuantity,
    required this.outstandingQuantity,
    required this.unitPrice,
    required this.amount,
    required this.remark,
  });

  factory PurchaseOrderItemModel.fromJson(Map<String, dynamic> json) {
    return PurchaseOrderItemModel(
      id: json['id'] as int,
      productCode: json['product_code'].toString(),
      partName: json['part_name'].toString(),
      partNo: json['part_no'].toString(),
      description: json['description'].toString(),
      quantityGrams: _number(json['quantity_grams']),
      unit: json['unit'].toString(),
      receivedQuantity: _number(json['received_quantity']),
      outstandingQuantity: _number(json['outstanding_quantity']),
      unitPrice: _number(json['unit_price']),
      amount: _number(json['amount']),
      remark: json['remark']?.toString() ?? '',
    );
  }

  final int id;
  final String productCode;
  final String partName;
  final String partNo;
  final String description;
  final double quantityGrams;
  final String unit;
  final double receivedQuantity;
  final double outstandingQuantity;
  final double unitPrice;
  final double amount;
  final String remark;
}

class PurchaseOrderModel {
  const PurchaseOrderModel({
    required this.poNumber,
    required this.poDate,
    required this.supplierCode,
    required this.supplierName,
    required this.quotationReference,
    required this.quotationDate,
    required this.requestedDeliveryDate,
    required this.deliveryPlantCode,
    required this.deliveryPlantName,
    required this.deliveryAddress,
    required this.notes,
    required this.paymentTermsDays,
    required this.paymentDueDate,
    required this.subtotal,
    required this.discountAmount,
    required this.ppnRate,
    required this.ppnAmount,
    required this.pph23Rate,
    required this.pph23Amount,
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

  factory PurchaseOrderModel.fromJson(Map<String, dynamic> json) {
    return PurchaseOrderModel(
      poNumber: json['po_number'].toString(),
      poDate: DateTime.parse(json['po_date'].toString()),
      supplierCode: json['supplier_code'].toString(),
      supplierName: json['supplier_name'].toString(),
      quotationReference: json['quotation_reference']?.toString(),
      quotationDate: json['quotation_date'] == null
          ? null
          : DateTime.parse(json['quotation_date'].toString()),
      requestedDeliveryDate: DateTime.parse(
        json['requested_delivery_date'].toString(),
      ),
      deliveryPlantCode: json['delivery_plant_code'].toString(),
      deliveryPlantName: json['delivery_plant_name'].toString(),
      deliveryAddress: json['delivery_address'].toString(),
      notes: json['notes']?.toString() ?? '',
      paymentTermsDays: json['payment_terms_days'] as int,
      paymentDueDate: DateTime.parse(json['payment_due_date'].toString()),
      subtotal: _number(json['subtotal']),
      discountAmount: _number(json['discount_amount']),
      ppnRate: _number(json['ppn_rate']),
      ppnAmount: _number(json['ppn_amount']),
      pph23Rate: _number(json['pph23_rate']),
      pph23Amount: _number(json['pph23_amount']),
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
                PurchaseOrderItemModel.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
    );
  }

  final String poNumber;
  final DateTime poDate;
  final String supplierCode;
  final String supplierName;
  final String? quotationReference;
  final DateTime? quotationDate;
  final DateTime requestedDeliveryDate;
  final String deliveryPlantCode;
  final String deliveryPlantName;
  final String deliveryAddress;
  final String notes;
  final int paymentTermsDays;
  final DateTime paymentDueDate;
  final double subtotal;
  final double discountAmount;
  final double ppnRate;
  final double ppnAmount;
  final double pph23Rate;
  final double pph23Amount;
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
  final List<PurchaseOrderItemModel> items;

  String get partNames => items.map((item) => item.partName).join(', ');
  String get partNumbers => items.map((item) => item.partNo).join(', ');
  String get remarks => items
      .map((item) => item.remark)
      .where((remark) => remark.isNotEmpty)
      .join(', ');
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

String purchaseOrderStatusLabel(String status) => switch (status) {
  'waiting_review' => 'Waiting Review',
  'approved' => 'Approved',
  'rejected' => 'Rejected',
  _ => status,
};
