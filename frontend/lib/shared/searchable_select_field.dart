import 'package:flutter/material.dart';

/// A form select for reference/master data.
///
/// Unlike [DropdownButtonFormField], this never truncates a long list into a
/// platform menu and it keeps the same validation contract as a normal form
/// field.  Callers provide a stable value and a label so objects/maps do not
/// rely on identity equality.
class SearchableSelectField<T> extends FormField<T> {
  SearchableSelectField({
    super.key,
    required T? value,
    required List<SearchableSelectOption<T>> options,
    required String labelText,
    required ValueChanged<T?>? onChanged,
    super.validator,
    super.enabled = true,
    String searchHint = 'Search',
    String emptyMessage = 'No matching options.',
    bool allowClear = false,
    String? helperText,
  }) : super(
         initialValue: value,
         builder: (state) {
           final selected = options.where(
             (option) => option.value == state.value,
           );
           final label = selected.isEmpty ? null : selected.first.label;
           final placeholder = 'Select ${_fieldName(labelText)}';
           return InkWell(
             borderRadius: BorderRadius.circular(4),
             onTap: !enabled || onChanged == null
                 ? null
                 : () async {
                     final selectedValue = await _showSearchableSelectDialog<T>(
                       state.context,
                       title: labelText,
                       options: options,
                       selectedValue: state.value,
                       searchHint: searchHint,
                       emptyMessage: emptyMessage,
                       allowClear: allowClear,
                     );
                     if (!state.context.mounted || selectedValue.noChange) {
                       return;
                     }
                     state.didChange(selectedValue.value);
                     onChanged(selectedValue.value);
                   },
             child: InputDecorator(
               // A placeholder is rendered as child content.  Keeping this
               // false makes InputDecorator float its label above that
               // content rather than painting both at the same baseline.
               isEmpty: false,
               decoration: InputDecoration(
                 labelText: labelText,
                 helperText: helperText,
                 errorText: state.errorText,
                 enabled: enabled && onChanged != null,
                 suffixIcon: const Icon(Icons.search),
               ),
               child: Text(
                 label ?? placeholder,
                 maxLines: 1,
                 overflow: TextOverflow.ellipsis,
                 style: label == null
                     ? const TextStyle(color: Color(0xFF667085))
                     : null,
               ),
             ),
           );
         },
       );
}

class SearchableSelectOption<T> {
  const SearchableSelectOption({
    required this.value,
    required this.label,
    this.searchTerms = const [],
  });

  final T value;
  final String label;
  final List<String> searchTerms;

  bool matches(String query) {
    final normalized = _normalize(query);
    if (normalized.isEmpty) return true;
    return _normalize(label).contains(normalized) ||
        searchTerms.any((term) => _normalize(term).contains(normalized));
  }
}

class _SelectResult<T> {
  const _SelectResult._(this.value, this.noChange);
  const _SelectResult.value(T? value) : this._(value, false);
  const _SelectResult.unchanged() : this._(null, true);

  final T? value;
  final bool noChange;
}

Future<_SelectResult<T>> _showSearchableSelectDialog<T>(
  BuildContext context, {
  required String title,
  required List<SearchableSelectOption<T>> options,
  required T? selectedValue,
  required String searchHint,
  required String emptyMessage,
  required bool allowClear,
}) async {
  final result = await showDialog<_SelectResult<T>>(
    context: context,
    builder: (dialogContext) => _SearchableSelectDialog<T>(
      title: title,
      options: options,
      selectedValue: selectedValue,
      searchHint: searchHint,
      emptyMessage: emptyMessage,
      allowClear: allowClear,
    ),
  );
  return result ?? _SelectResult<T>.unchanged();
}

class _SearchableSelectDialog<T> extends StatefulWidget {
  const _SearchableSelectDialog({
    required this.title,
    required this.options,
    required this.selectedValue,
    required this.searchHint,
    required this.emptyMessage,
    required this.allowClear,
  });

  final String title;
  final List<SearchableSelectOption<T>> options;
  final T? selectedValue;
  final String searchHint;
  final String emptyMessage;
  final bool allowClear;

  @override
  State<_SearchableSelectDialog<T>> createState() =>
      _SearchableSelectDialogState<T>();
}

class _SearchableSelectDialogState<T>
    extends State<_SearchableSelectDialog<T>> {
  final _query = TextEditingController();

  @override
  void initState() {
    super.initState();
    _query.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = widget.options
        .where((option) => option.matches(_query.text))
        .toList(growable: false);
    final dialog = AlertDialog(
      title: Text(widget.title),
      content: SizedBox(
        width: 520,
        height: 440,
        child: Column(
          children: [
            TextField(
              controller: _query,
              autofocus: true,
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                hintText: widget.searchHint,
                suffixIcon: _query.text.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Clear search',
                        onPressed: _query.clear,
                        icon: const Icon(Icons.clear),
                      ),
              ),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: filtered.isEmpty
                  ? Center(child: Text(widget.emptyMessage))
                  : Scrollbar(
                      thumbVisibility: true,
                      child: ListView.builder(
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          final option = filtered[index];
                          final isSelected =
                              option.value == widget.selectedValue;
                          return ListTile(
                            title: Text(option.label),
                            trailing: isSelected
                                ? const Icon(
                                    Icons.check,
                                    color: Color(0xFF4F659F),
                                  )
                                : null,
                            onTap: () => Navigator.pop(
                              context,
                              _SelectResult<T>.value(option.value),
                            ),
                          );
                        },
                      ),
                    ),
            ),
          ],
        ),
      ),
      actions: [
        if (widget.allowClear && widget.selectedValue != null)
          TextButton(
            onPressed: () =>
                Navigator.pop(context, _SelectResult<T>.value(null)),
            child: const Text('Clear'),
          ),
        TextButton(
          onPressed: () => Navigator.pop(context, _SelectResult<T>.unchanged()),
          child: const Text('Cancel'),
        ),
      ],
    );
    return LayoutBuilder(
      builder: (context, constraints) => constraints.maxWidth < 600
          ? Dialog.fullscreen(child: SafeArea(child: dialog))
          : dialog,
    );
  }
}

String _normalize(String value) => value.toLowerCase().trim();

String _fieldName(String label) => label.replaceFirst(RegExp(r'\s*\*\s*$'), '');
