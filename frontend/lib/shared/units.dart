const inventoryUnits = ['pcs', 'bar', 'liter', 'pail', 'ton', 'kg', 'gram'];
const discreteUnits = {'pcs', 'bar', 'pail'};

String unitLabel(String unit) => unit == 'gram' ? 'grams' : unit;

bool isDiscreteUnit(String unit) => discreteUnits.contains(unit);

/// Validates an inventory quantity while keeping fractional values available
/// for weight and volume units.
String? quantityValidationError(
  String? value,
  String unit, {
  bool allowZero = false,
}) {
  final quantity = double.tryParse(value?.trim() ?? '');
  if (quantity == null || (allowZero ? quantity < 0 : quantity <= 0)) {
    return allowZero
        ? 'Enter zero or greater'
        : 'Enter a quantity greater than zero';
  }
  if (isDiscreteUnit(unit) && quantity != quantity.roundToDouble()) {
    return 'Quantity must be a whole number for $unit';
  }
  return null;
}

String formatQuantity(Object? value, String unit) {
  final numeric = switch (value) {
    num number => number,
    _ => num.tryParse(value?.toString() ?? ''),
  };
  if (numeric == null) return value?.toString() ?? '-';
  if (isDiscreteUnit(unit)) return numeric.toStringAsFixed(0);
  final formatted = numeric.toStringAsFixed(3);
  return formatted
      .replaceFirst(RegExp(r'0+$'), '')
      .replaceFirst(RegExp(r'\.$'), '');
}
