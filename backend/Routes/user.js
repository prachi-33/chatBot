import express from 'express';
import { prisma } from "../index.js";
const router=express.Router();
import { createUserSchema, updateUserSchema } from "../schemas/userSchema.js";
import authenticate from "../middlewares/auth.js";


// POST /api/user - Create user
router.post("/create", authenticate, async (req, res) => {
  const result = createUserSchema.safeParse(req.body);
  if (!result.success) {
    return res.status(400).json({ error: result.error.errors });
  }

  const { id,email, name } = req.body;

  try {
    const existing = await prisma.user.findUnique({ where: { email } });
    if (existing) return res.status(409).json({ error: "User already exists" });

    const user = await prisma.user.create({ data: { id,email, name } });
    return res.status(201).json(user);
  } catch (err) {
    return res.status(500).json({ error: "Failed to create user" });
  }
});

// GET /api/user/me - Get current user
router.get("/me/:id", authenticate, async (req, res) => {
  try {
    const id = req.params.id;
    const userData = await prisma.user.findUnique({
      where: { id: id }
    });

    if (!userData) return res.status(404).json({ error: "User not found" });

    res.json(userData);
  } catch (err) {
    res.status(500).json({ error: "Failed to fetch user" });
  }
});


export default router;
