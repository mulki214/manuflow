import 'package:erp_manufaktur/features/users/user_model.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('maps complete user detail and derives display identity', () {
    final user = UserModel.fromJson({
      'id': '110826000',
      'first_name': 'Andi',
      'last_name': 'Mulki',
      'email': 'andi@example.com',
      'gender': 'male',
      'role': 'Administrator',
      'ktp_number': '1234567890123456',
      'is_active': true,
      'created_at': '2026-08-11T08:00:00Z',
      'updated_at': '2026-08-11T09:00:00Z',
      'access_level': 'head',
      'department_code': 'PROD',
      'department_name': 'Production',
      'pic_name': 'Budi PIC',
      'head_name': 'Sari Head',
      'can_edit': true,
      'can_delete': true,
    });

    expect(user.fullName, 'Andi Mulki');
    expect(user.initials, 'AM');
    expect(user.createdAt.toUtc(), DateTime.utc(2026, 8, 11, 8));
    expect(user.updatedAt.toUtc(), DateTime.utc(2026, 8, 11, 9));
    expect(user.departmentName, 'Production');
    expect(user.picName, 'Budi PIC');
    expect(user.headName, 'Sari Head');
    expect(user.canEdit, isTrue);
  });
}
