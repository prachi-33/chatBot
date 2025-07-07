import dotenv from "dotenv";
dotenv.config();
import express from 'express';
import cors from "cors";
import { createClient } from '@supabase/supabase-js';
import { PrismaClient } from '@prisma/client';
import authenticate from "./middlewares/auth.js";
import mainRouter from "./Routes/index.js";

// Initialize clients
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);
const prisma = new PrismaClient();

const app = express();
const port = process.env.PORT || 3000;

const allowedOrigins = ['http://localhost:5173'];
app.use(cors({
  origin: allowedOrigins,
  credentials: true
}));

// Middleware
app.use(express.json());
app.use("/api",mainRouter);

app.use(authenticate);



// Start server
app.listen(port, () => {
  console.log(`Server running on PORT ${port}`);
});

// Export for use in other files
export {
  supabase,
  prisma
};