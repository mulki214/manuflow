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

  testWidgets('select follows an externally changed value', (tester) async {
    String? selectedValue = 'SUP-01';
    await tester.pumpWidget(
      MaterialApp(
        home: StatefulBuilder(
          builder: (context, setState) => Scaffold(
            body: Column(
              children: [
                SearchableSelectField<String>(
                  value: selectedValue,
                  labelText: 'Supplier *',
                  options: const [
                    SearchableSelectOption(
                      value: 'SUP-01',
                      label: 'SUP-01 — Supplier',
                    ),
                  ],
                  onChanged: (_) {},
                ),
                TextButton(
                  onPressed: () => setState(() => selectedValue = null),
                  child: const Text('Clear selection'),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    expect(find.text('SUP-01 — Supplier'), findsOneWidget);
    await tester.tap(find.text('Clear selection'));
    await tester.pump();
    expect(find.text('Select Supplier'), findsOneWidget);
  });

  testWidgets('keyed item rows keep the right selection after middle removal', (
    tester,
  ) async {
    final lines = <_TestLine>[_TestLine('A'), _TestLine('B'), _TestLine('C')];
    await tester.pumpWidget(
      MaterialApp(
        home: StatefulBuilder(
          builder: (context, setState) => Scaffold(
            body: Column(
              children: [
                for (var index = 0; index < lines.length; index++)
                  Card(
                    key: ObjectKey(lines[index]),
                    child: Row(
                      children: [
                        Expanded(
                          child: SearchableSelectField<String>(
                            value: lines[index].code,
                            labelText: 'Product ${lines[index].code}',
                            options: [
                              SearchableSelectOption(
                                value: lines[index].code,
                                label: 'Product ${lines[index].code}',
                              ),
                            ],
                            onChanged: (_) {},
                          ),
                        ),
                        IconButton(
                          onPressed: () => setState(() {
                            lines.removeAt(index);
                          }),
                          icon: const Icon(Icons.delete_outline),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.byType(IconButton).at(1));
    await tester.pumpAndSettle();

    expect(find.text('Product A'), findsWidgets);
    expect(find.text('Product B'), findsNothing);
    expect(find.text('Product C'), findsWidgets);
  });
}

class _TestLine {
  _TestLine(this.code);

  final String code;
}
