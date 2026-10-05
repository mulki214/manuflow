import 'package:erp_manufaktur/shared/searchable_select_field.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Widget subject({String? value}) => MaterialApp(
    home: Scaffold(
      body: SearchableSelectField<String>(
        value: value,
        labelText: 'Supplier *',
        options: const [
          SearchableSelectOption(value: 'SUP-01', label: 'SUP-01 — Supplier'),
        ],
        onChanged: (_) {},
      ),
    ),
  );

  testWidgets('empty select floats label above a clean placeholder', (
    tester,
  ) async {
    await tester.pumpWidget(subject());

    expect(find.text('Supplier *'), findsOneWidget);
    expect(find.text('Select Supplier'), findsOneWidget);
    expect(
      tester.widget<InputDecorator>(find.byType(InputDecorator)).isEmpty,
      isFalse,
    );
  });

  testWidgets('selected select keeps the label floated and shows its value', (
    tester,
  ) async {
    await tester.pumpWidget(subject(value: 'SUP-01'));

    expect(find.text('Supplier *'), findsOneWidget);
    expect(find.text('SUP-01 — Supplier'), findsOneWidget);
    expect(
      tester.widget<InputDecorator>(find.byType(InputDecorator)).isEmpty,
      isFalse,
    );
  });
}
