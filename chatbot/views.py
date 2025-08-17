from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from .services import GLMChatbot

@method_decorator(csrf_exempt, name='dispatch')
class ChatbotView(View):
    def get(self, request):
        return render(request, 'chatbot/chat.html')
    
    def post(self, request):
        try:
            user_message = request.POST.get('message', '')
            
            if not user_message:
                return JsonResponse({'error': 'Mesaj boş'}, status=400)
            
            chatbot = GLMChatbot()
            response = chatbot.generate_response(user_message)
            
            return JsonResponse({'response': response})
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error in chatbot view: {error_details}")
            return JsonResponse({'error': f'Sunucu hatası: {str(e)}'}, status=500)