from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import MediaFile
from .serializers import MediaFileSerializer
import cloudinary.uploader
import cloudinary.api


# Helper: session check
def is_authenticated(request):
    return request.session.get("authenticated", False)


class UnlockView(APIView):
    def post(self, request):
        try:
            print("DEBUG: request.data =", request.data)
            password = request.data.get("password")
            print("DEBUG: password =", password)
            print("DEBUG: settings.GALLERY_PASSWORD =", getattr(settings, "GALLERY_PASSWORD", None))

            if password == settings.GALLERY_PASSWORD:
                request.session["authenticated"] = True
                request.session.save()
                return Response({"message": "Unlocked!"}, status=status.HTTP_200_OK)

            return Response({"error": "Invalid password"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)



class MediaListView(APIView):
    """
    Always fetches live images from Cloudinary.
    Supports pagination via ?cursor=<next_cursor>
    """

    def get(self, request):
        if not is_authenticated(request):
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            # pagination support
            cursor = request.query_params.get("cursor")

            result = cloudinary.api.resources(
                type="upload",
                resource_type="image",
                max_results=50,   # change per-page size if needed
                next_cursor=cursor
            )

            images = [
                {
                    "url": r["secure_url"],
                    "filename": r["public_id"]
                }
                for r in result.get("resources", [])
            ]

            return Response({
                "images": images,
                "next_cursor": result.get("next_cursor")  # frontend can use this for "Load More"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UploadView(APIView):
    def post(self, request):
        if not is_authenticated(request):
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        files = request.FILES.getlist("images")
        if not files:
            return Response({"error": "No files uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        uploaded = []
        for f in files:
            try:
                res = cloudinary.uploader.upload(f, resource_type="image")
                # save optional record in DB (not required if always pulling from Cloudinary)
                media = MediaFile.objects.create(
                    filename=f.name,
                    url=res["secure_url"]
                )
                uploaded.append(media)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = MediaFileSerializer(uploaded, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
