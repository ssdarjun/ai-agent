import React from 'react';

const Product = ({ product }) => {
  return (
    <div className="group bg-white rounded-xl shadow-sm hover:shadow-xl transition-all duration-300 border border-gray-100 overflow-hidden flex flex-col h-full">
      <div className="relative aspect-square overflow-hidden bg-gray-100">
        <img 
          src={product.image || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&q=80&w=400'} 
          alt={product.title} 
          className="w-full h-full object-cover transform group-hover:scale-110 transition-transform duration-500"
        />
        <div className="absolute top-3 right-3">
          <button className="bg-white/80 backdrop-blur-sm p-2 rounded-full text-gray-600 hover:text-red-500 transition-colors shadow-sm">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
          </button>
        </div>
      </div>
      
      <div className="p-5 flex flex-col flex-grow text-left">
        <div className="mb-2">
          <span className="text-xs font-bold text-blue-600 uppercase tracking-wider bg-blue-50 px-2 py-1 rounded">
            {product.category || 'Featured'}
          </span>
        </div>
        <h3 className="text-lg font-bold text-gray-800 mb-2 line-clamp- group-hover:text-blue-600 transition-colors">
          {product.title}
        </h3>
        <p className="text-gray-500 text-sm mb-4 line-clamp-2 flex-grow leading-relaxed">
          {product.description || 'Premium quality product designed for durability and style.'}
        </p>
        
        <div className="flex items-center justify-between mt-auto">
          <span className="text-2xl font-black text-gray-900">
            ${product.price}
          </span>
          {/*
          <button className="bg-gray-900 text-white px-4 py-2 rounded-lg font-semibold text-sm hover:bg-blue-600 transition-colors active:scale-95 transform">
            Add to Cart
          </button>
          */}
        </div>
      </div>
    </div>
  );
};

export default Product;
