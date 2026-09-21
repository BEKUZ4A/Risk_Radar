from django.core.management.base import BaseCommand, CommandError

from apps.users.models import User


class Command(BaseCommand):
    help = 'Promote an existing user to full Django administrator access.'

    def add_arguments(self, parser):
        parser.add_argument('email', help='Email address of the user to promote')

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as exc:
            raise CommandError(f'User with email {email!r} was not found.') from exc

        user.role = User.Role.OWNER
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=['role', 'is_staff', 'is_superuser'])

        self.stdout.write(
            self.style.SUCCESS(
                f'{email} is now an OWNER and full Django superuser.'
            )
        )
