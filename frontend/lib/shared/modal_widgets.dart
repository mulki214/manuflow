import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Scroll view for dialog content with a visible, draggable vertical thumb.
class ModalScrollView extends StatefulWidget {
  const ModalScrollView({super.key, required this.child, this.padding});

  final Widget child;
  final EdgeInsetsGeometry? padding;

  @override
  State<ModalScrollView> createState() => _ModalScrollViewState();
}

class _ModalScrollViewState extends State<ModalScrollView> {
  final _controller = ScrollController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scrollbar(
    controller: _controller,
    thumbVisibility: true,
    interactive: true,
    child: SelectionArea(
      child: SingleChildScrollView(
        controller: _controller,
        primary: false,
        padding: widget.padding,
        child: widget.child,
      ),
    ),
  );
}

/// Horizontal scrolling for wide dialog tables, with a visible scrollbar.
class ModalHorizontalScroll extends StatefulWidget {
  const ModalHorizontalScroll({super.key, required this.child});

  final Widget child;

  @override
  State<ModalHorizontalScroll> createState() => _ModalHorizontalScrollState();
}

class _ModalHorizontalScrollState extends State<ModalHorizontalScroll> {
  final _controller = ScrollController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scrollbar(
    controller: _controller,
    thumbVisibility: true,
    interactive: true,
    notificationPredicate: (notification) =>
        notification.metrics.axis == Axis.horizontal,
    child: SingleChildScrollView(
      controller: _controller,
      primary: false,
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.only(bottom: 12),
      child: widget.child,
    ),
  );
}

bool isCodeDetailLabel(String label) {
  final normalized = label.toLowerCase();
  return normalized.contains('code') ||
      normalized.contains('number') ||
      normalized.contains('lot') ||
      normalized.contains('document') ||
      normalized.contains('reference') ||
      normalized.contains('customer po') ||
      normalized.contains('quotation') ||
      normalized.contains('user id') ||
      normalized.contains('ktp');
}

class CopyableCodeText extends StatelessWidget {
  const CopyableCodeText(this.value, {super.key, this.style});

  final String value;
  final TextStyle? style;

  Future<void> _copy(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!context.mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text('$value copied')));
  }

  @override
  Widget build(BuildContext context) {
    if (value.isEmpty || value == '-') return Text(value, style: style);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Flexible(child: SelectableText(value, style: style)),
        IconButton(
          tooltip: 'Copy',
          visualDensity: VisualDensity.compact,
          iconSize: 18,
          onPressed: () => _copy(context),
          icon: const Icon(Icons.content_copy_outlined),
        ),
      ],
    );
  }
}

class DetailValue extends StatelessWidget {
  const DetailValue({
    super.key,
    required this.label,
    required this.value,
    this.style,
  });

  final String label;
  final String value;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) => isCodeDetailLabel(label)
      ? CopyableCodeText(value, style: style)
      : SelectableText(value, style: style);
}
