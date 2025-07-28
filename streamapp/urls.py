from django.urls import path
from .views import index, detail_anime, all_list_anime_terbaru, all_list_jadwal_rilis, all_list_movie, detail_episode_video, search, user_collection
app_name = 'streamapp'
urlpatterns = [
    path('', index, name='index'),
    path('anime/<str:anime_slug>/', detail_anime, name='detail_anime'),
    path('all-anime-terbaru/', all_list_anime_terbaru, name='all_list_anime_terbaru'),
    path('jadwal-rilis/', all_list_jadwal_rilis, name='all_list_jadwal_rilis'),
    path('movie/', all_list_movie, name='all_list_movie'),
    path('episode/<path:episode_slug>/', detail_episode_video, name='detail_episode_video'),
    path('search/', search, name='search'),
    path('koleksi/', user_collection, name='user_collection')
]