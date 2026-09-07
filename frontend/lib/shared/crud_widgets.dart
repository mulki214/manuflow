import 'package:flutter/material.dart';

/// Keeps wide desktop data tables usable without clipping later rows.
/// The outer viewport scrolls rows, while the inner one scrolls columns.
class ScrollableDataTable extends StatelessWidget {
  const ScrollableDataTable({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => Scrollbar(
    child: SingleChildScrollView(
      primary: false,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        primary: false,
        child: child,
      ),
    ),
  );
}

Future<bool> showDeleteConfirmation(
  BuildContext context, {
  required String title,
  required String message,
}) async {
  return await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(title),
          content: Text(message),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.error,
              ),
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Delete'),
            ),
          ],
        ),
      ) ??
      false;
}

class CrudPaginationBar extends StatelessWidget {
  const CrudPaginationBar({
    super.key,
    required this.currentPage,
    required this.totalPages,
    required this.totalRecords,
    required this.onPrevious,
    required this.onNext,
  });

  final int currentPage;
  final int totalPages;
  final int totalRecords;
  final VoidCallback? onPrevious;
  final VoidCallback? onNext;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Row(
        children: [
          Expanded(
            child: Text(
              'Page $currentPage of $totalPages • $totalRecords records',
              style: const TextStyle(color: Color(0xFF667085)),
            ),
          ),
          IconButton.outlined(
            tooltip: 'Previous page',
            onPressed: onPrevious,
            icon: const Icon(Icons.chevron_left),
          ),
          const SizedBox(width: 8),
          IconButton.outlined(
            tooltip: 'Next page',
            onPressed: onNext,
            icon: const Icon(Icons.chevron_right),
          ),
        ],
      ),
    );
  }
}
