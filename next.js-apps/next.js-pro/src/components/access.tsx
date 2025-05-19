"use client"

import { useState } from "react"

import { RiGithubFill, RiGoogleFill } from "@remixicon/react"
import { GalleryVerticalEnd, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { signIn } from "@/lib/auth/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function Component() {
  const [loader, setLoader] = useState<"email" | "github" | "google" | null>(null)

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button className="w-24 cursor-pointer" size="sm" variant="outline">
          Login
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md sm:max-w-md">
        <DialogHeader className="sr-only">
          <DialogTitle className="text-center">Login</DialogTitle>
        </DialogHeader>
        <div className="w-full">
          <div className="flex flex-col gap-6">
            <form>
              <div className="flex flex-col gap-6">
                <div className="flex flex-col items-center gap-2">
                  <a href="#" className="flex flex-col items-center gap-2 font-medium">
                    <div className="flex size-8 items-center justify-center rounded-md">
                      <GalleryVerticalEnd className="size-6" />
                    </div>
                    <span className="sr-only">ACME Inc.</span>
                  </a>
                  <h1 className="text-xl font-bold">Welcome to ACME Inc.</h1>
                </div>
                <div className="flex flex-col gap-6">
                  <div className="grid gap-3">
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" type="email" placeholder="m@example.com" required />
                  </div>
                  <Button
                    type="submit"
                    className="w-full cursor-pointer"
                    onClick={async () => {
                      setLoader("email")
                      toast.info("Login with email is not implemented yet!")
                      setLoader(null)
                    }}
                    disabled={loader === "email"}
                  >
                    {loader === "email" ? <Loader2 className="size-5 animate-spin" /> : null}
                    Login
                  </Button>
                </div>
                <div className="after:border-border relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t">
                  <span className="bg-background text-muted-foreground relative z-10 px-2">Or</span>
                </div>
                <div className="grid gap-4">
                  <Button
                    variant="outline"
                    type="button"
                    className="w-full cursor-pointer"
                    onClick={async () => {
                      setLoader("github")
                      const res = await signIn.social({
                        provider: "github",
                        callbackURL: "/x",
                      })
                      if (res.error) {
                        toast.error(res.error.message)
                        setLoader(null)
                      }
                    }}
                    disabled={loader === "github"}
                  >
                    {loader === "github" ? (
                      <Loader2 className="size-5 animate-spin" />
                    ) : (
                      <RiGithubFill className="size-5" />
                    )}
                    Continue with Github
                  </Button>
                  <Button
                    variant="outline"
                    type="button"
                    className="w-full cursor-pointer"
                    onClick={async () => {
                      setLoader("google")
                      const res = await signIn.social({
                        provider: "google",
                        callbackURL: "/x",
                      })
                      if (res.error) {
                        toast.error(res.error.message)
                        setLoader(null)
                      }
                    }}
                    disabled={loader === "google"}
                  >
                    {loader === "google" ? (
                      <Loader2 className="size-5 animate-spin" />
                    ) : (
                      <RiGoogleFill className="size-5" />
                    )}
                    Continue with Google
                  </Button>
                </div>
              </div>
            </form>
            <div className="text-muted-foreground *:[a]:hover:text-primary text-center text-xs text-balance *:[a]:underline *:[a]:underline-offset-4">
              By clicking continue, you agree to our <a href="#">Terms of Service</a> and{" "}
              <a href="#">Privacy Policy</a>.
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
