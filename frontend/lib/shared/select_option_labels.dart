/// Consistent, human-readable labels for reference-data selectors.
///
/// The code remains first for traceability, while the name and description
/// make it safe for an operator to choose between similarly coded records.
String productSelectLabel(Map<String, dynamic> product) => _join([
  _text(product['code'] ?? product['product_code']),
  _text(product['part_name'] ?? product['product_name']),
  _text(product['description']),
]);

String lotSelectLabel(Map<String, dynamic> lot, {required String quantity}) =>
    _join([
      productSelectLabel(lot),
      'Lot ${_text(lot['lot_number'])}',
      quantity,
    ]);

String storageLocationSelectLabel(Map<String, dynamic> location) => _join([
  _text(location['storage_name']),
  _text(location['code']),
  _text(location['name']),
]);

String transportationSelectLabel(Map<String, dynamic> vehicle) => _join([
  _text(vehicle['code']),
  _text(vehicle['vehicle_number']),
  _text(vehicle['carrier_name']),
]);

String orderItemSelectLabel(
  Map<String, dynamic> item, {
  required String quantity,
}) => _join([
  _text(item['document_number']),
  _text(item['product_name'] ?? item['part_name'] ?? item['product_code']),
  _text(item['product_description'] ?? item['description']),
  quantity,
]);

String _join(Iterable<String> values) {
  final seen = <String>{};
  return values
      .where((value) => value.isNotEmpty && seen.add(value.toLowerCase()))
      .join(' — ');
}

String _text(dynamic value) => value?.toString().trim() ?? '';
