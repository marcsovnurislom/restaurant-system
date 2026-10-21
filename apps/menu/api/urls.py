from rest_framework.routers import SimpleRouter

from apps.menu.api.views import CategoryViewSet, DishViewSet, TagViewSet

app_name = "menu-api"

router = SimpleRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("tags", TagViewSet, basename="tag")
router.register("dishes", DishViewSet, basename="dish")

urlpatterns = router.urls
