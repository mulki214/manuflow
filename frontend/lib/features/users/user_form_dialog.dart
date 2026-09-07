import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../master_data/master_data_models.dart';
import 'user_model.dart';

class UserFormDialog extends StatefulWidget {
  const UserFormDialog({super.key, required this.api, this.user});

  final ApiClient api;
  final UserModel? user;

  @override
  State<UserFormDialog> createState() => _UserFormDialogState();
}

class _UserFormDialogState extends State<UserFormDialog> {
  final _formKey = GlobalKey<FormState>();
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _email = TextEditingController();
  final _role = TextEditingController();
  final _ktp = TextEditingController();
  final _password = TextEditingController();
  String _gender = 'male';
  String _accessLevel = 'staff';
  String? _departmentCode;
  List<LookupOption> _departments = [];
  bool _loadingLookups = true;
  bool _saving = false;
  bool _obscure = true;
  String? _error;

  bool get _editing => widget.user != null;

  @override
  void initState() {
    super.initState();
    final user = widget.user;
    if (user != null) {
      _firstName.text = user.firstName;
      _lastName.text = user.lastName;
      _email.text = user.email;
      _role.text = user.role;
      _ktp.text = user.ktpNumber;
      _gender = user.gender;
      _accessLevel = user.accessLevel;
      _departmentCode = user.departmentCode;
    }
    _loadDepartments();
  }

  Future<void> _loadDepartments() async {
    try {
      final response = await widget.api.getJson(
        '/master-data/departments?size=100',
      );
      _departments = (response['items'] as List)
          .map(
            (item) => LookupOption(
              code: item['code'] as String,
              name: item['name'] as String,
            ),
          )
          .toList();
    } on ApiException catch (exception) {
      _error = exception.message;
    } finally {
      if (mounted) setState(() => _loadingLookups = false);
    }
  }

  @override
  void dispose() {
    for (final controller in [
      _firstName,
      _lastName,
      _email,
      _role,
      _ktp,
      _password,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    final body = <String, dynamic>{
      'first_name': _firstName.text.trim(),
      'last_name': _lastName.text.trim(),
      'email': _email.text.trim(),
      'gender': _gender,
      'role': _role.text.trim(),
      'department_code': _departmentCode,
      'access_level': _accessLevel,
      'ktp_number': _ktp.text.trim(),
      if (_password.text.isNotEmpty) 'password': _password.text,
    };
    try {
      if (_editing) {
        await widget.api.patchJson('/users/${widget.user!.id}', body);
      } else {
        await widget.api.postJson('/users', body);
      }
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Tidak dapat terhubung ke server');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 700;
    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 680, maxHeight: 780),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        _editing ? 'Update User' : 'Tambah User',
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: _saving ? null : () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
                Text(
                  _editing
                      ? 'ID user tidak dapat diubah. Kosongkan password jika tidak ingin menggantinya.'
                      : 'ID user dibuat otomatis saat data disimpan.',
                  style: const TextStyle(color: Color(0xFF667085)),
                ),
                const SizedBox(height: 24),
                if (_loadingLookups) const LinearProgressIndicator(),
                if (_loadingLookups) const SizedBox(height: 18),
                _ResponsiveFields(
                  wide: wide,
                  children: [
                    _field(_firstName, 'Nama depan', validator: _required),
                    _field(_lastName, 'Nama belakang'),
                    _field(
                      _email,
                      'Email',
                      keyboardType: TextInputType.emailAddress,
                      validator: (value) =>
                          value == null || !value.contains('@')
                          ? 'Email tidak valid'
                          : null,
                    ),
                    DropdownButtonFormField<String>(
                      initialValue: _gender,
                      decoration: const InputDecoration(
                        labelText: 'Jenis kelamin',
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'male',
                          child: Text('Laki-laki'),
                        ),
                        DropdownMenuItem(
                          value: 'female',
                          child: Text('Perempuan'),
                        ),
                      ],
                      onChanged: (value) => setState(() => _gender = value!),
                    ),
                    DropdownButtonFormField<String>(
                      initialValue:
                          const [
                            'Staff',
                            'Head',
                            'Courier',
                            'Warehouse',
                            'Production',
                            'QC',
                            'Purchasing',
                            'Sales',
                            'Administrator',
                          ].contains(_role.text)
                          ? _role.text
                          : null,
                      decoration: const InputDecoration(
                        labelText: 'Position / Role',
                      ),
                      items: const [
                        DropdownMenuItem(value: 'Staff', child: Text('Staff')),
                        DropdownMenuItem(value: 'Head', child: Text('Head')),
                        DropdownMenuItem(
                          value: 'Courier',
                          child: Text('Courier'),
                        ),
                        DropdownMenuItem(
                          value: 'Warehouse',
                          child: Text('Warehouse'),
                        ),
                        DropdownMenuItem(
                          value: 'Production',
                          child: Text('Production'),
                        ),
                        DropdownMenuItem(value: 'QC', child: Text('QC')),
                        DropdownMenuItem(
                          value: 'Purchasing',
                          child: Text('Purchasing'),
                        ),
                        DropdownMenuItem(value: 'Sales', child: Text('Sales')),
                        DropdownMenuItem(
                          value: 'Administrator',
                          child: Text('Administrator'),
                        ),
                      ],
                      onChanged: (value) =>
                          setState(() => _role.text = value ?? ''),
                      validator: (value) => value == null ? 'Required' : null,
                    ),
                    DropdownButtonFormField<String>(
                      initialValue:
                          _departments.any(
                            (item) => item.code == _departmentCode,
                          )
                          ? _departmentCode
                          : null,
                      decoration: const InputDecoration(
                        labelText: 'Department',
                      ),
                      items: _departments
                          .map(
                            (item) => DropdownMenuItem(
                              value: item.code,
                              child: Text(
                                item.label,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (value) =>
                          setState(() => _departmentCode = value),
                      validator: (value) =>
                          value == null ? 'Wajib dipilih' : null,
                    ),
                    DropdownButtonFormField<String>(
                      initialValue: _accessLevel,
                      decoration: const InputDecoration(
                        labelText: 'Access Level',
                      ),
                      items: const [
                        DropdownMenuItem(value: 'staff', child: Text('Staff')),
                        DropdownMenuItem(value: 'head', child: Text('Head')),
                        DropdownMenuItem(
                          value: 'administrator',
                          child: Text('Administrator'),
                        ),
                      ],
                      onChanged: (value) =>
                          setState(() => _accessLevel = value!),
                    ),
                    _field(
                      _ktp,
                      'Nomor KTP',
                      keyboardType: TextInputType.number,
                      maxLength: 16,
                      validator: (value) =>
                          value == null || !RegExp(r'^\d{16}$').hasMatch(value)
                          ? 'Harus 16 digit angka'
                          : null,
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _password,
                  obscureText: _obscure,
                  decoration: InputDecoration(
                    labelText: _editing
                        ? 'Password baru (opsional)'
                        : 'Password',
                    helperText: _editing
                        ? 'Biarkan kosong untuk mempertahankan password lama'
                        : 'Minimal 8 karakter',
                    suffixIcon: IconButton(
                      onPressed: () => setState(() => _obscure = !_obscure),
                      icon: Icon(
                        _obscure
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                    ),
                  ),
                  validator: (value) {
                    if (!_editing && (value == null || value.length < 8)) {
                      return 'Password minimal 8 karakter';
                    }
                    if (_editing &&
                        value != null &&
                        value.isNotEmpty &&
                        value.length < 8) {
                      return 'Password minimal 8 karakter';
                    }
                    return null;
                  },
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton(
                      onPressed: _saving ? null : () => Navigator.pop(context),
                      child: const Text('Batal'),
                    ),
                    const SizedBox(width: 10),
                    FilledButton(
                      onPressed: _saving || _loadingLookups ? null : _save,
                      child: _saving
                          ? const SizedBox.square(
                              dimension: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : Text(_editing ? 'Simpan Perubahan' : 'Simpan User'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    String? Function(String?)? validator,
    TextInputType? keyboardType,
    int? maxLength,
  }) {
    return TextFormField(
      controller: controller,
      decoration: InputDecoration(labelText: label, counterText: ''),
      validator: validator,
      keyboardType: keyboardType,
      maxLength: maxLength,
    );
  }

  String? _required(String? value) =>
      value == null || value.trim().isEmpty ? 'Wajib diisi' : null;
}

class _ResponsiveFields extends StatelessWidget {
  const _ResponsiveFields({required this.wide, required this.children});
  final bool wide;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    if (!wide) {
      return Column(
        children: children
            .expand((child) => [child, const SizedBox(height: 14)])
            .toList(),
      );
    }
    return Wrap(
      spacing: 14,
      runSpacing: 14,
      children: children
          .map((child) => SizedBox(width: 302, child: child))
          .toList(),
    );
  }
}
