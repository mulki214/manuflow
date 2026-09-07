import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import 'production_models.dart';

class ProductionProcessFormDialog extends StatefulWidget {
  const ProductionProcessFormDialog({
    super.key,
    required this.api,
    this.process,
  });

  final ApiClient api;
  final ProductionProcessModel? process;

  @override
  State<ProductionProcessFormDialog> createState() =>
      _ProductionProcessFormDialogState();
}

class _ProductionProcessFormDialogState
    extends State<ProductionProcessFormDialog> {
  final _key = GlobalKey<FormState>();
  late final TextEditingController _code;
  late final TextEditingController _name;
  late final TextEditingController _description;
  List<Map<String, dynamic>> _plants = [];
  String? _plantCode;
  String _type = 'production';
  bool _active = true;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _code = TextEditingController(text: widget.process?.code ?? '');
    _name = TextEditingController(text: widget.process?.name ?? '');
    _description = TextEditingController(
      text: widget.process?.description ?? '',
    );
    _plantCode = widget.process?.plantCode;
    _type = widget.process?.type ?? 'production';
    _active = widget.process?.isActive ?? true;
    _load();
  }

  Future<void> _load() async {
    try {
      final result = await widget.api.getJson(
        '/master-data/plants?page=1&size=100',
      );
      if (mounted) {
        setState(
          () =>
              _plants = (result['items'] as List).cast<Map<String, dynamic>>(),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _code.dispose();
    _name.dispose();
    _description.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_key.currentState!.validate()) return;
    setState(() => _saving = true);
    final payload = {
      if (widget.process == null) 'code': _code.text.trim().toUpperCase(),
      'name': _name.text.trim(),
      'description': _description.text.trim(),
      'process_type': _type,
      'plant_code': _plantCode,
      'is_active': _active,
    };
    try {
      if (widget.process == null) {
        await widget.api.postJson('/production/processes', payload);
      } else {
        await widget.api.patchJson(
          '/production/processes/${widget.process!.code}',
          payload,
        );
      }
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.process == null
          ? 'Create Production Process'
          : 'Update Production Process',
    ),
    content: SizedBox(
      width: 560,
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : Form(
              key: _key,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (_error != null)
                      Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    TextFormField(
                      controller: _code,
                      enabled: widget.process == null,
                      decoration: const InputDecoration(
                        labelText: 'Process Code *',
                      ),
                      validator: (value) =>
                          (value ?? '').trim().isEmpty ? 'Required' : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _name,
                      decoration: const InputDecoration(
                        labelText: 'Process Name *',
                      ),
                      validator: (value) =>
                          (value ?? '').trim().isEmpty ? 'Required' : null,
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: _type,
                      decoration: const InputDecoration(
                        labelText: 'Process Type *',
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'production',
                          child: Text('Production'),
                        ),
                        DropdownMenuItem(
                          value: 'repair',
                          child: Text('Repair'),
                        ),
                      ],
                      onChanged: (value) =>
                          setState(() => _type = value ?? 'production'),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: _plantCode,
                      decoration: const InputDecoration(labelText: 'Plant *'),
                      items: _plants
                          .map(
                            (item) => DropdownMenuItem(
                              value: item['code'].toString(),
                              child: Text('${item['code']} — ${item['name']}'),
                            ),
                          )
                          .toList(),
                      onChanged: (value) => setState(() => _plantCode = value),
                      validator: (value) => value == null ? 'Required' : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _description,
                      minLines: 2,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        labelText: 'Process Description',
                      ),
                    ),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      value: _active,
                      onChanged: (value) => setState(() => _active = value),
                      title: const Text('Active'),
                    ),
                  ],
                ),
              ),
            ),
    ),
    actions: [
      TextButton(
        onPressed: _saving ? null : () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: _saving ? null : _save,
        child: Text(widget.process == null ? 'Create' : 'Update'),
      ),
    ],
  );
}
