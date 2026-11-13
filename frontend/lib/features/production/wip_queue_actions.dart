import 'package:flutter/material.dart';

/// Keeps the WIP queue's desktop actions on one line so they cannot overlap
/// the next DataTable row.
class WipQueueActions extends StatelessWidget {
  const WipQueueActions({
    super.key,
    required this.canProcess,
    required this.canTransfer,
    required this.onProcess,
    required this.onTransfer,
  });

  final bool canProcess;
  final bool canTransfer;
  final VoidCallback onProcess;
  final VoidCallback onTransfer;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      FilledButton(
        style: FilledButton.styleFrom(
          minimumSize: const Size(0, 40),
          padding: const EdgeInsets.symmetric(horizontal: 12),
          visualDensity: VisualDensity.compact,
        ),
        onPressed: canProcess ? onProcess : null,
        child: const Text('Process'),
      ),
      if (canTransfer) ...[
        const SizedBox(width: 8),
        OutlinedButton.icon(
          style: OutlinedButton.styleFrom(
            minimumSize: const Size(0, 40),
            padding: const EdgeInsets.symmetric(horizontal: 12),
            visualDensity: VisualDensity.compact,
          ),
          onPressed: onTransfer,
          icon: const Icon(Icons.swap_horiz, size: 18),
          label: const Text('Transfer Plant'),
        ),
      ],
    ],
  );
}
