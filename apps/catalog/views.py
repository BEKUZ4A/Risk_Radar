from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.users.models import User
from apps.users.permissions import IsOwnerOrCustomer, is_root_user
from apps.risks.services import RiskEngineService

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryListCreateAPIView(APIView):
    """Katalog kategoriyalari — faqat OWNER/CUSTOMER."""

    permission_classes = [IsOwnerOrCustomer]

    @extend_schema(responses={200: CategorySerializer(many=True)})
    def get(self, request):
        qs = Category.objects.all()
        return Response(CategorySerializer(qs, many=True).data)

    @extend_schema(request=CategorySerializer, responses={201: CategorySerializer})
    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        obj = serializer.save(created_by=request.user)
        return Response(CategorySerializer(obj).data, status=201)


class CategoryDetailAPIView(APIView):
    permission_classes = [IsOwnerOrCustomer]

    @extend_schema(responses={200: CategorySerializer, 404: dict})
    def get_object(self, pk):
        return Category.objects.filter(pk=pk).first()

    @extend_schema(responses={200: CategorySerializer, 404: dict})
    def get(self, request, pk):
        obj = self.get_object(pk)
        if not obj:
            return Response({'error': 'Kategoriya topilmadi.'}, status=404)
        return Response(CategorySerializer(obj).data)

    @extend_schema(request=CategorySerializer, responses={200: CategorySerializer, 400: dict, 404: dict})
    def put(self, request, pk):
        obj = self.get_object(pk)
        if not obj:
            return Response({'error': 'Kategoriya topilmadi.'}, status=404)
        serializer = CategorySerializer(obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(responses={204: None, 403: dict, 404: dict})
    def delete(self, request, pk):
        if not is_root_user(request.user) and request.user.role != User.Role.OWNER:
            return Response({'error': 'Faqat OWNER o‘chira oladi.'}, status=403)
        obj = self.get_object(pk)
        if not obj:
            return Response({'error': 'Kategoriya topilmadi.'}, status=404)
        obj.delete()
        return Response(status=204)


class ProductListCreateAPIView(APIView):
    """Mahsulotlar — faqat OWNER/CUSTOMER."""

    permission_classes = [IsOwnerOrCustomer]

    @extend_schema(responses={200: ProductSerializer(many=True)})
    def get(self, request):
        qs = Product.objects.select_related('category').filter(is_active=True)
        category_id = request.query_params.get('category')
        if category_id:
            qs = qs.filter(category_id=category_id)
        return Response(ProductSerializer(qs, many=True).data)

    @extend_schema(request=ProductSerializer, responses={201: ProductSerializer})
    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        obj = serializer.save(created_by=request.user)
        RiskEngineService.process_catalog_product_change(product=obj, action='CREATE')
        return Response(ProductSerializer(obj).data, status=201)


class ProductDetailAPIView(APIView):
    permission_classes = [IsOwnerOrCustomer]

    @extend_schema(responses={200: ProductSerializer, 404: dict})
    def get_object(self, pk):
        return Product.objects.select_related('category').filter(pk=pk).first()

    @extend_schema(responses={200: ProductSerializer, 404: dict})
    def get(self, request, pk):
        obj = self.get_object(pk)
        if not obj:
            return Response({'error': 'Mahsulot topilmadi.'}, status=404)
        return Response(ProductSerializer(obj).data)

    @extend_schema(request=ProductSerializer, responses={200: ProductSerializer, 400: dict, 404: dict})
    def put(self, request, pk):
        obj = self.get_object(pk)
        if not obj:
            return Response({'error': 'Mahsulot topilmadi.'}, status=404)
        old_price = obj.price
        serializer = ProductSerializer(obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        obj = serializer.save()
        RiskEngineService.process_catalog_product_change(
            product=obj,
            old_price=old_price,
            action='UPDATE',
        )
        return Response(serializer.data)

    @extend_schema(responses={200: dict, 403: dict, 404: dict})
    def delete(self, request, pk):
        if not is_root_user(request.user) and request.user.role != User.Role.OWNER:
            return Response({'error': 'Faqat OWNER o‘chira oladi.'}, status=403)
        obj = self.get_object(pk)
        if not obj:
            return Response({'error': 'Mahsulot topilmadi.'}, status=404)
        obj.is_active = False
        obj.save(update_fields=['is_active'])
        return Response({'message': 'Mahsulot deaktiv qilindi.'})
