import 'package:erp_manufaktur/shared/crud_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('table wrapper provides vertical and horizontal viewports', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SizedBox(
            height: 100,
            child: ScrollableDataTable(child: Text('Many table rows')),
          ),
        ),
      ),
    );

    final viewports = tester.widgetList<SingleChildScrollView>(
      find.byType(SingleChildScrollView),
    );
    expect(viewports, hasLength(2));
    expect(viewports.first.scrollDirection, Axis.vertical);
    expect(viewports.last.scrollDirection, Axis.horizontal);
  });
}
