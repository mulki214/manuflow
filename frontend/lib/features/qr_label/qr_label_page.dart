import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../../shared/product_qr_label_dialog.dart';
import '../../shared/searchable_select_field.dart';
import '../../shared/select_option_labels.dart';
import '../auth/auth_controller.dart';

class QrLabelPage extends StatefulWidget {
  const QrLabelPage({super.key, required this.auth});
  final AuthController auth;
  @override
  State<QrLabelPage> createState() => _QrLabelPageState();
}

class _QrLabelPageState extends State<QrLabelPage> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String _search = '';
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final result = await widget.auth.api.getJson(
        '/qr-labels?page=1&size=100&search=${Uri.encodeQueryComponent(_search)}',
      );
      if (mounted) {
        setState(
          () => _items = (result['items'] as List).cast<Map<String, dynamic>>(),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _edit([Map<String, dynamic>? item]) async {
    final changed = await showDialog<bool>(
      context: context,
      builder: (_) => _QrLabelForm(api: widget.auth.api, item: item),
    );
    if (changed == true) _load();
  }

  Future<void> _delete(Map<String, dynamic> item) async {
    await widget.auth.api.delete('/qr-labels/${item['id']}');
    await _load();
  }

  @override
  Widget build(BuildContext context) => AppModuleScaffold(
    auth: widget.auth,
    activeModule: AppModule.qrLabel,
    title: 'QR Label',
    floatingActionButton: FloatingActionButton.extended(
      onPressed: () => _edit(),
      icon: const Icon(Icons.add),
      label: const Text('Create QR Label'),
    ),
    body: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'QR Label',
            style: Theme.of(
              context,
            ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          const Text(
            'Create independent QR labels from free text or master data.',
            style: TextStyle(color: Color(0xFF667085)),
          ),
          const SizedBox(height: 16),
          TextField(
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search),
              hintText: 'Search label or QR text',
            ),
            onSubmitted: (v) {
              _search = v;
              _load();
            },
          ),
          const SizedBox(height: 16),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _items.isEmpty
                ? const Center(child: Text('No QR Labels found.'))
                : ListView.separated(
                    itemCount: _items.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 10),
                    itemBuilder: (_, i) {
                      final item = _items[i];
                      return Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: LayoutBuilder(
                            builder: (_, c) {
                              final actions = Wrap(
                                spacing: 4,
                                children: [
                                  IconButton(
                                    tooltip: 'Preview / download',
                                    icon: const Icon(Icons.qr_code_2_outlined),
                                    onPressed: () => _preview(item),
                                  ),
                                  IconButton(
                                    tooltip: 'Edit',
                                    icon: const Icon(Icons.edit_outlined),
                                    onPressed: () => _edit(item),
                                  ),
                                  IconButton(
                                    tooltip: 'Delete',
                                    icon: const Icon(Icons.delete_outline),
                                    onPressed: () => _delete(item),
                                  ),
                                ],
                              );
                              final text = Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    item['label_name'].toString(),
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  SelectableText(
                                    item['resolved_text'].toString(),
                                    maxLines: 2,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Template: ${item['template']}\nCreated by ${item['created_by_name']}',
                                    style: const TextStyle(
                                      color: Color(0xFF667085),
                                      fontSize: 12,
                                    ),
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ],
                              );
                              return c.maxWidth < 560
                                  ? Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        text,
                                        Align(
                                          alignment: Alignment.centerRight,
                                          child: actions,
                                        ),
                                      ],
                                    )
                                  : Row(
                                      children: [
                                        Expanded(child: text),
                                        actions,
                                      ],
                                    );
                            },
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    ),
  );
  void _preview(Map<String, dynamic> item) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => _QrLabelPreview(
        name: item['label_name'].toString(),
        text: item['resolved_text'].toString(),
      ),
    ),
  );
}

class _QrLabelForm extends StatefulWidget {
  const _QrLabelForm({required this.api, this.item});
  final ApiClient api;
  final Map<String, dynamic>? item;
  @override
  State<_QrLabelForm> createState() => _QrLabelFormState();
}

class _QrLabelFormState extends State<_QrLabelForm> {
  late final TextEditingController _name = TextEditingController(
    text: widget.item?['label_name']?.toString() ?? '',
  );
  late final TextEditingController _template = TextEditingController(
    text: widget.item?['template']?.toString() ?? '',
  );
  List<Map<String, dynamic>> _products = [], _plants = [];
  Map<String, dynamic>? _product, _plant;
  bool _saving = false;
  @override
  void initState() {
    super.initState();
    _template.addListener(() => setState(() {}));
    _load();
  }

  Future<void> _load() async {
    final r = await Future.wait([
      widget.api.getJson('/master-data/products?page=1&size=100'),
      widget.api.getJson('/master-data/plants?page=1&size=100'),
    ]);
    if (mounted) {
      setState(() {
        _products = (r[0]['items'] as List).cast<Map<String, dynamic>>();
        _plants = (r[1]['items'] as List).cast<Map<String, dynamic>>();
      });
    }
  }

  String get _resolved {
    var text = _template.text;
    final values = {
      '{date}': DateTime.now().toIso8601String().substring(0, 10),
      '{product_code}': _product?['code']?.toString() ?? '',
      '{product_name}': _product?['part_name']?.toString() ?? '',
      '{part_no}': _product?['part_no']?.toString() ?? '',
      '{plant_code}': _plant?['code']?.toString() ?? '',
      '{plant_name}': _plant?['name']?.toString() ?? '',
    };
    values.forEach((k, v) => text = text.replaceAll(k, v));
    return text;
  }

  void _token(String value) {
    _template.text = '${_template.text}$value';
    _template.selection = TextSelection.collapsed(
      offset: _template.text.length,
    );
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty ||
        _resolved.trim().isEmpty ||
        _resolved.contains(RegExp(r'\{[^}]+\}'))) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Enter a label name and resolve every template token.'),
        ),
      );
      return;
    }
    setState(() => _saving = true);
    try {
      final body = {
        'label_name': _name.text.trim(),
        'template': _template.text.trim(),
        'resolved_text': _resolved.trim(),
      };
      if (widget.item == null) {
        await widget.api.postJson('/qr-labels', body);
      } else {
        await widget.api.patchJson('/qr-labels/${widget.item!['id']}', body);
      }
      if (mounted) {
        Navigator.pop(context, true);
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.item == null ? 'Create QR Label' : 'Edit QR Label'),
    content: SizedBox(
      width: 680,
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'Label Name *'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _template,
              minLines: 3,
              maxLines: 5,
              decoration: const InputDecoration(
                labelText: 'QR Text Template *',
                hintText: '{product_code}-{date}-ABC-001',
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children:
                  [
                        '{date}',
                        '{product_code}',
                        '{product_name}',
                        '{part_no}',
                        '{plant_code}',
                        '{plant_name}',
                      ]
                      .map(
                        (x) => ActionChip(
                          label: Text(x),
                          onPressed: () => _token(x),
                        ),
                      )
                      .toList(),
            ),
            const SizedBox(height: 16),
            SearchableSelectField<Map<String, dynamic>>(
              value: _product,
              labelText: 'Product (optional)',
              allowClear: true,
              options: _products
                  .map(
                    (p) => SearchableSelectOption(
                      value: p,
                      label: productSelectLabel(p),
                      searchTerms: [
                        p['code'].toString(),
                        p['part_name']?.toString() ?? '',
                      ],
                    ),
                  )
                  .toList(),
              onChanged: (v) => setState(() => _product = v),
            ),
            const SizedBox(height: 12),
            SearchableSelectField<Map<String, dynamic>>(
              value: _plant,
              labelText: 'Plant (optional)',
              allowClear: true,
              options: _plants
                  .map(
                    (p) => SearchableSelectOption(
                      value: p,
                      label: '${p['code']} — ${p['name']}',
                      searchTerms: [
                        p['code'].toString(),
                        p['name']?.toString() ?? '',
                      ],
                    ),
                  )
                  .toList(),
              onChanged: (v) => setState(() => _plant = v),
            ),
            const SizedBox(height: 18),
            const Text(
              'Resolved Text',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            SelectableText(_resolved.isEmpty ? '—' : _resolved),
            const SizedBox(height: 12),
            Center(
              child: Container(
                color: Colors.white,
                padding: const EdgeInsets.all(12),
                child: QrPayloadImage(
                  data: 'MANUFLOW-LABEL|$_resolved',
                  size: 180,
                ),
              ),
            ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: _saving ? null : _save,
        child: Text(_saving ? 'Saving…' : 'Save QR Label'),
      ),
    ],
  );
}

class _QrLabelPreview extends StatefulWidget {
  const _QrLabelPreview({required this.name, required this.text});
  final String name, text;

  @override
  State<_QrLabelPreview> createState() => _QrLabelPreviewState();
}

class _QrLabelPreviewState extends State<_QrLabelPreview> {
  bool _downloading = false;

  Future<void> _download() async {
    setState(() => _downloading = true);
    try {
      final image = await QrPainter(
        data: 'MANUFLOW-LABEL|${widget.text}',
        version: QrVersions.auto,
        gapless: false,
      ).toImageData(768, format: ui.ImageByteFormat.png);
      if (image == null) throw StateError('QR image could not be rendered');
      await FileSaver.instance.saveFile(
        name:
            'qr-label-${widget.name.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '-')}',
        bytes: Uint8List.view(image.buffer),
        fileExtension: 'png',
        mimeType: MimeType.png,
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to download this QR Label.')),
        );
      }
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('QR Label')),
    body: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(widget.name, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          SelectableText(widget.text),
          const SizedBox(height: 18),
          Container(
            color: Colors.white,
            padding: const EdgeInsets.all(12),
            child: QrPayloadImage(
              data: 'MANUFLOW-LABEL|${widget.text}',
              size: 280,
            ),
          ),
          const SizedBox(height: 18),
          FilledButton.icon(
            onPressed: _downloading ? null : _download,
            icon: const Icon(Icons.download),
            label: Text(_downloading ? 'Preparing…' : 'Download PNG'),
          ),
        ],
      ),
    ),
  );
}
