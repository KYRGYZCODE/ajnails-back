from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from .models import User
from .serializers import CustomTokenObtainPairSerializer, CustomTokenRefreshSerializer, UserRegistration, UserSerializer, FireUser


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ('set_current_warehouse'):
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get("project_id")
        show_fired = self.request.query_params.get("show_fired")

        if project_id:
            queryset = queryset.filter(projectaccess__project_id=project_id)
        
        if show_fired:
            queryset = queryset.filter(is_fired=True)
        else:
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'fire':
            return FireUser
        if self.action == 'register_user':
            return UserRegistration
        return super().get_serializer_class()
    
    @action(methods=['post'], detail=True)
    def fire(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        termination_reason = request.data.get('termination_reason')
        termination_order_date = request.data.get('termination_order_date')
        termination_date = request.data.get('termination_date')
        user.fire(reason=termination_reason, order_date=termination_order_date, termination_date=termination_date)
        return Response({'message': 'user fired'}, status=status.HTTP_200_OK)
    
    @action(methods=['post'], detail=True)
    def restore(self, request, pk=None):
        user = get_object_or_404(User, pk=pk, is_fired=True)
        user.restore()
        return Response({'message': 'user restored'}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def register_user(self, request):
        serializer = UserRegistration(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)



class RegisterView(APIView):
    @swagger_auto_schema(
        operation_summary="Регистрация",
        operation_description='Регистрация пользователей. Письмо на почту не отправляется, юзер является активным.\nОбязательные поля: email, password. Поле role можно указать из этих вариантов: ["worker", "manager", "director"], по умолчанию worker.',
        request_body=UserRegistration,
    )
    def post(self, request):
        serializer = UserRegistration(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)

            return Response({
                    'user': serializer.data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer
