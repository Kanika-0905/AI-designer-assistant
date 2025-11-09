from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import io
import requests
from PIL import Image
import json
import os
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

USER_DATA_FILE = 'user_data.json'
COLLECTIONS_DIR = 'collections'
os.makedirs(COLLECTIONS_DIR, exist_ok=True)

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {'collections': [], 'downloads': []}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def remove_watermark(image):
    try:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        width, height = image.size
        clean_height = height - 50
        clean_image = image.crop((0, 0, width, clean_height))
        clean_image = clean_image.resize((width, height), Image.Resampling.LANCZOS)
        
        return clean_image
    except:
        return image

def build_enhanced_prompt(prompt, category, specifications):
    """Build enhanced prompt with specifications"""
    
    base_prompts = {
        'dress': f"fashion design sketch, {prompt} dress, elegant fashion illustration, haute couture, detailed clothing design",
        'jewelry': f"luxury jewelry design, {prompt} jewelry, precious stones, professional jewelry photography, detailed accessories",
        'home_decor': f"interior design, {prompt} home decor, modern furniture, room design, architectural visualization"
    }
    
    enhanced_prompt = base_prompts.get(category, f"{prompt} {category} design")
    
    # Add specifications to prompt
    if category == 'dress':
        if 'fabric' in specifications:
            enhanced_prompt += f", {specifications['fabric']} fabric"
        if 'style' in specifications:
            enhanced_prompt += f", {specifications['style']} style dress"
    
    elif category == 'jewelry':
        if 'stone' in specifications:
            enhanced_prompt += f", {specifications['stone']} stone"
        if 'metal' in specifications:
            enhanced_prompt += f", {specifications['metal']} metal"
        if 'style' in specifications:
            enhanced_prompt += f", {specifications['style']} jewelry style"
    
    elif category == 'home_decor':
        if 'material' in specifications:
            enhanced_prompt += f", {specifications['material']} material"
        if 'room' in specifications:
            enhanced_prompt += f", {specifications['room']} furniture"
        if 'style' in specifications:
            enhanced_prompt += f", {specifications['style']} interior style"
    
    # Add budget-based quality terms
    budget_terms = {
        'low': 'affordable, budget-friendly, simple design',
        'medium': 'mid-range, quality design, balanced',
        'high': 'premium, high-quality, sophisticated',
        'luxury': 'luxury, high-end, exclusive, premium materials'
    }
    
    if 'budget' in specifications:
        enhanced_prompt += f", {budget_terms.get(specifications['budget'], '')}"
    
    enhanced_prompt += ", professional design, high quality, detailed"
    
    return enhanced_prompt

def generate_with_pollinations(prompt, category, specifications):
    try:
        enhanced_prompt = build_enhanced_prompt(prompt, category, specifications)
        api_url = f"https://image.pollinations.ai/prompt/{enhanced_prompt}"
        
        print(f"Enhanced prompt: {enhanced_prompt}")
        
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        
        image = Image.open(io.BytesIO(response.content))
        image = image.convert('RGB')
        
        clean_image = remove_watermark(image)
        clean_image = clean_image.resize((512, 512), Image.Resampling.LANCZOS)
        
        return clean_image
        
    except Exception as e:
        print(f"AI error: {e}")
        return None

@app.route('/', methods=['GET'])
def home():
    return jsonify({'message': 'Advanced AI Designer is running!'})

@app.route('/api/generate', methods=['POST'])
def generate_design():
    try:
        data = request.json
        prompt = data.get('prompt', 'design')
        category = data.get('category', 'dress')
        specifications = data.get('specifications', {})
        
        print(f"Generating: {prompt} ({category}) with specs: {specifications}")
        
        image = generate_with_pollinations(prompt, category, specifications)
        
        if not image:
            return jsonify({'success': False, 'message': 'Failed to generate image'})
        
        design_id = str(uuid.uuid4())
        image_path = os.path.join(COLLECTIONS_DIR, f"{design_id}.png")
        image.save(image_path)
        
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        user_data = load_user_data()
        design_info = {
            'id': design_id,
            'prompt': prompt,
            'category': category,
            'specifications': specifications,
            'created_at': datetime.now().isoformat(),
            'image_path': image_path
        }
        user_data['collections'].append(design_info)
        save_user_data(user_data)
        
        return jsonify({
            'success': True,
            'message': f'Generated custom {category} design',
            'image': f'data:image/png;base64,{img_str}',
            'design_id': design_id,
            'specifications': specifications
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/collections', methods=['GET'])
def get_collections():
    try:
        user_data = load_user_data()
        collections = []
        
        for design in user_data['collections']:
            if os.path.exists(design['image_path']):
                with open(design['image_path'], 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode()
                
                collections.append({
                    'id': design['id'],
                    'prompt': design['prompt'],
                    'category': design['category'],
                    'specifications': design.get('specifications', {}),
                    'created_at': design['created_at'],
                    'image': f'data:image/png;base64,{img_data}'
                })
        
        return jsonify({'success': True, 'collections': collections})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/download/<design_id>', methods=['GET'])
def download_design(design_id):
    try:
        user_data = load_user_data()
        
        design = None
        for d in user_data['collections']:
            if d['id'] == design_id:
                design = d
                break
        
        if not design or not os.path.exists(design['image_path']):
            return jsonify({'success': False, 'message': 'Design not found'})
        
        download_info = {
            'design_id': design_id,
            'prompt': design['prompt'],
            'category': design['category'],
            'specifications': design.get('specifications', {}),
            'downloaded_at': datetime.now().isoformat()
        }
        user_data['downloads'].append(download_info)
        save_user_data(user_data)
        
        with open(design['image_path'], 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()
        
        return jsonify({
            'success': True,
            'image': f'data:image/png;base64,{img_data}',
            'filename': f"{design['prompt']}_{design['category']}.png"
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/profile', methods=['GET'])
def get_profile():
    try:
        user_data = load_user_data()
        
        stats = {
            'total_designs': len(user_data['collections']),
            'total_downloads': len(user_data['downloads']),
            'categories': {},
            'budget_breakdown': {},
            'recent_activity': []
        }
        
        for design in user_data['collections']:
            category = design['category']
            stats['categories'][category] = stats['categories'].get(category, 0) + 1
            
            # Budget breakdown
            budget = design.get('specifications', {}).get('budget', 'unknown')
            stats['budget_breakdown'][budget] = stats['budget_breakdown'].get(budget, 0) + 1
        
        recent = sorted(user_data['collections'], key=lambda x: x['created_at'], reverse=True)[:10]
        stats['recent_activity'] = recent
        
        return jsonify({'success': True, 'profile': stats})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

if __name__ == '__main__':
    print("Starting Advanced AI Designer...")
    app.run(debug=True, host='0.0.0.0', port=5000)
