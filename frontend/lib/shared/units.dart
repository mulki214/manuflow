const inventoryUnits = ['pcs', 'bar', 'liter', 'pail', 'kg', 'gram'];
const discreteUnits = {'pcs', 'bar', 'pail'};

String unitLabel(String unit) => unit == 'gram' ? 'grams' : unit;

bool isDiscreteUnit(String unit) => discreteUnits.contains(unit);

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
