import 'package:erp_manufaktur/features/production/wip_queue_actions.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('queue actions stay on one row at their reserved width', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 390,
            child: WipQueueActions(
              canProcess: true,
              canTransfer: true,
              onProcess: () {},
              onTransfer: () {},
            ),
          ),
        ),
      ),
    );

    final process = tester.getRect(find.text('Process'));
    final transfer = tester.getRect(find.text('Transfer Plant'));
    expect(process.top, transfer.top);
    expect(tester.takeException(), isNull);
  });

  testWidgets('non-production jobs show Process without transfer action', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: WipQueueActions(
            canProcess: false,
            canTransfer: false,
            onProcess: () {},
            onTransfer: () {},
          ),
        ),
      ),
    );

    expect(find.text('Process'), findsOneWidget);
    expect(find.text('Transfer Plant'), findsNothing);
    expect(
      tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
      isNull,
    );
  });
}
